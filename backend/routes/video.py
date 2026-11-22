import re
import requests
from flask import Blueprint, jsonify, request
from config import BASE_URL, SIBLING_COURSE_MAP
from crypto_utils import decrypt_val
from disha_client import make_disha_request
from cache_manager import (
    get_cached_video, save_cached_video, execute_coalesced
)

video_bp = Blueprint("video", __name__)

@video_bp.route("/api/batch/<course_id>/video/<video_id>", methods=["GET"])
def api_batch_video(course_id, video_id):
    clean_id = str(course_id).split("_")[-1] if "_" in str(course_id) else str(course_id)
    effective_id = SIBLING_COURSE_MAP.get(clean_id, {}).get("hostCourseId", clean_id)

    # 1. Check Video Cache first (Reusable for YouTube and unexpiring HLS streams)
    cached = get_cached_video(effective_id, video_id)
    if cached:
        # If it's YouTube or static direct HLS stream, cache is 100% safe to reuse
        if cached.get("ytFlag") == 1 or (cached.get("hls_url") and not cached.get("embed_player_url")):
            return jsonify(cached)
        # Appx embed_player_url uses single-use tokens, so we resolve fresh token below

    def _resolve_video():
        hls_stream = ""
        yt_id = ""
        yt_flag = 0
        embed_player_url = ""
        debug_collected = {}

        # Step 1: Check if video is currently a live broadcast
        try:
            status_url = f"{BASE_URL}get/course_contents_by_live_status?course_id={effective_id}"
            r_status = make_disha_request(status_url, course_id=effective_id).json()
            for lv in r_status.get("data", {}).get("live", []):
                if str(lv.get("id")) == str(video_id):
                    live_links = lv.get("livestream_links", [])
                    if live_links and isinstance(live_links, list):
                        first_p = live_links[0].get("path") or ""
                        if first_p:
                            dec_p = decrypt_val(first_p)
                            if ".m3u8" in dec_p.lower():
                                hls_stream = dec_p
                    if not hls_stream:
                        dec_f = decrypt_val(lv.get("file_link") or lv.get("recording_hls") or "")
                        if ".m3u8" in dec_f.lower():
                            hls_stream = dec_f
                    break
        except Exception as lv_err:
            debug_collected["live_check_err"] = str(lv_err)

        # Step 2: Rate-paced request to official endpoint with auto-rotated course token
        if not embed_player_url and not hls_stream and not yt_id:
            try:
                u = f"{BASE_URL}get/fetchVideoDetailsById?course_id={effective_id}&video_id={video_id}&ytflag=0&folder_wise_course=1"
                r = make_disha_request(u, course_id=effective_id)
                if r.status_code == 200:
                    res_json = r.json()
                    data = res_json.get("data", {})
                    if isinstance(data, dict):
                        # A. Check Appx video_player_token
                        tok = str(data.get("video_player_token") or "").strip()
                        if tok and tok != "1234":
                            base_p = str(data.get("video_player_url") or "")
                            if not base_p or "token=" not in base_p:
                                base_p = "https://appx-play.classx.co.in/combined-img-player?isMobile=true&token="
                            embed_player_url = f"/combined-img-player?isMobile=true&token={tok}"

                        # B. Check direct file_link or video_id
                        raw_link = data.get("file_link") or data.get("video_id") or ""
                        if raw_link:
                            dec = decrypt_val(raw_link)
                            if ".m3u8" in dec.lower():
                                if not hls_stream:
                                    hls_stream = dec
                            elif dec and not dec.startswith("http") and not yt_id:
                                yt_id = dec
                                yt_flag = 1
                            elif ("youtube.com" in dec or "youtu.be" in dec) and not yt_id:
                                m = re.search(r"(?:v=|\/|embed\/)([0-9A-Za-z_-]{11})", dec)
                                if m:
                                    yt_id = m.group(1)
                                    yt_flag = 1

                        # C. Check encrypted_links for HLS m3u8
                        enc_links = data.get("encrypted_links", [])
                        if enc_links and isinstance(enc_links, list):
                            for el in enc_links:
                                first_path = el.get("path") or el.get("backup_url") or el.get("url") or ""
                                if first_path:
                                    dec_stream = decrypt_val(first_path)
                                    if ".m3u8" in dec_stream.lower() and not hls_stream:
                                        hls_stream = dec_stream

                        # D. Check recording_hls
                        if not hls_stream and data.get("recording_hls"):
                            hls_stream = data.get("recording_hls")
            except Exception as ex:
                debug_collected["primary_err"] = str(ex)

        # Step 3: Fallback via gbdoc API if local account was rate-limited or returned null
        if not embed_player_url and not hls_stream and not yt_id:
            try:
                fb_url = f"https://gbdoc.vercel.app/api/disha/video?batchId={effective_id}&lectureId={video_id}"
                fb_res = requests.get(fb_url, timeout=12).json()
                if fb_res.get("success") and fb_res.get("data"):
                    d = fb_res.get("data")
                    if d.get("videoId"):
                        yt_id = d.get("videoId")
                        yt_flag = 1
                    if d.get("streamUrl"):
                        hls_stream = d.get("streamUrl")
                    if d.get("embedUrl"):
                        e_u = d.get("embedUrl")
                        if "url=" in e_u:
                            raw_target = requests.utils.unquote(e_u.split("url=", 1)[1])
                            embed_player_url = f"/api/disha-player?url={requests.utils.quote(raw_target)}"
                        else:
                            embed_player_url = e_u
            except Exception as fb_err:
                debug_collected["gbdoc_fallback_err"] = str(fb_err)

        final_hls = hls_stream
        if hls_stream and ("transcoded-videos.classx.co.in" in hls_stream or "classx.co.in" in hls_stream):
            final_hls = f"/api/proxy-hls?url={requests.utils.quote(hls_stream)}"

        player_type = "youtube" if yt_id else ("embed" if embed_player_url else ("hls" if final_hls else ""))

        res_payload = {
            "status": 200,
            "video_id": yt_id,
            "hls_url": final_hls,
            "raw_hls_url": hls_stream,
            "embed_player_url": embed_player_url,
            "player_type": player_type,
            "ytFlag": yt_flag,
            "debug": debug_collected
        }

        # Cache static playable streams (YouTube and unexpiring HLS), but avoid caching single-use tokens permanently
        if yt_id or (final_hls and not embed_player_url):
            save_cached_video(effective_id, video_id, res_payload)

        return res_payload

    try:
        coalesce_key = f"video_{effective_id}_{video_id}"
        result = execute_coalesced(coalesce_key, _resolve_video)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": 500, "error": str(e)}), 500
