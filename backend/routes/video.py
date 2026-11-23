import re
import requests
from flask import Blueprint, jsonify, request
from config import BASE_URL, SIBLING_COURSE_MAP, VERIFIED_COURSE_OWNER_REDIRECT
from crypto_utils import decrypt_val, extract_pdf_from_raw
from disha_client import make_disha_request
from appx_hls import APPX_PLAY_ORIGIN, warm_and_extract_appx_token
from cache_manager import (
    get_cached_video, save_cached_video, execute_coalesced
)

video_bp = Blueprint("video", __name__)

@video_bp.route("/api/batch/<course_id>/video/<video_id>", methods=["GET"])
def api_batch_video(course_id, video_id):
    clean_id = str(course_id).split("_")[-1] if "_" in str(course_id) else str(course_id)
    effective_id = SIBLING_COURSE_MAP.get(clean_id, {}).get("hostCourseId") or VERIFIED_COURSE_OWNER_REDIRECT.get(clean_id, clean_id)

    # 1. Check Video Cache first (Reusable for YouTube and unexpiring HLS streams ONLY)
    cached = get_cached_video(effective_id, video_id)
    if cached:
        is_yt = cached.get("ytFlag") == 1 or cached.get("video_id")
        hls = cached.get("hls_url") or ""
        is_token_hls = "appx-hls" in hls or "token=" in hls
        if is_yt or (hls and not is_token_hls and not cached.get("embed_player_url")):
            return jsonify(cached)
        # For Appx streams, tokens must be warmed fresh or validated below

    def _resolve_video():
        hls_stream = ""
        yt_id = ""
        yt_flag = 0
        embed_player_url = ""
        qualities = []
        pdf_url = ""
        pdf_key = ""
        is_enc_pdf = False
        debug_collected = {}

        # Step 1: Check if video is currently a live broadcast
        try:
            status_url = f"{BASE_URL}get/course_contents_by_live_status?course_id={effective_id}"
            r_status = make_disha_request(status_url, course_id=effective_id).json()
            for lv in r_status.get("data", {}).get("live", []):
                if str(lv.get("id")) == str(video_id):
                    # Check PDF notes
                    p_url, p_k, p_enc = extract_pdf_from_raw(lv)
                    if p_url:
                        pdf_url, pdf_key, is_enc_pdf = p_url, p_k, p_enc

                    # Check encrypted livestream_links
                    live_links = lv.get("livestream_links", [])
                    if live_links and isinstance(live_links, list):
                        for ll in live_links:
                            for key in ["path", "backup_url", "backup_url2"]:
                                p = ll.get(key)
                                if p:
                                    dec_p = decrypt_val(p)
                                    if ".m3u8" in dec_p.lower():
                                        hls_stream = dec_p
                                        break
                                    elif ("youtube.com" in dec_p or "youtu.be" in dec_p) and not yt_id:
                                        m = re.search(r"(?:v=|\/|embed\/)([0-9A-Za-z_-]{11})", dec_p)
                                        if m:
                                            yt_id = m.group(1)
                                            yt_flag = 1
                            if hls_stream or yt_id:
                                break

                    # Check file_link or recording_hls or video_id or embed_url
                    for field in [lv.get("file_link"), lv.get("recording_hls"), lv.get("video_id"), lv.get("embed_url")]:
                        if not field: continue
                        dec_f = decrypt_val(field) if (":" in str(field) and not str(field).startswith("http")) else str(field).strip()
                        if not dec_f: continue
                        if ".m3u8" in dec_f.lower() and not hls_stream:
                            hls_stream = dec_f
                        elif ("youtube.com" in dec_f or "youtu.be" in dec_f) and not yt_id:
                            m = re.search(r"(?:v=|\/|embed\/)([0-9A-Za-z_-]{11})", dec_f)
                            if m:
                                yt_id = m.group(1)
                                yt_flag = 1
                        elif dec_f and not dec_f.startswith("http") and len(dec_f) == 11 and not yt_id:
                            yt_id = dec_f
                            yt_flag = 1

                    # Check video_player_token
                    tok = str(lv.get("video_player_token") or "").strip()
                    if tok and tok != "1234" and not hls_stream and not yt_id:
                        warmed = warm_and_extract_appx_token(tok)
                        if warmed:
                            hls_stream = f"/api/disha/appx-hls/master.m3u8?token={tok}"
                            q_map = warmed.get("qualities_map", {})
                            for q_lbl in ["1080p", "720p", "480p", "360p", "Auto"]:
                                if q_lbl in q_map:
                                    qualities.append({"quality": q_lbl, "url": f"/api/disha/appx-hls/{q_lbl}.m3u8?token={tok}&q={q_lbl}"})
                        else:
                            embed_player_url = f"/api/disha-player?url={requests.utils.quote(f'{APPX_PLAY_ORIGIN}/combined-img-player?isMobile=true&token={tok}')}"
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
                        # PDF Notes
                        p_url, p_k, p_enc = extract_pdf_from_raw(data)
                        if p_url:
                            pdf_url, pdf_key, is_enc_pdf = p_url, p_k, p_enc

                        # A. Check Appx video_player_token
                        tok = str(data.get("video_player_token") or "").strip()
                        if tok and tok != "1234":
                            warmed = warm_and_extract_appx_token(tok)
                            if warmed:
                                hls_stream = f"/api/disha/appx-hls/master.m3u8?token={tok}"
                                q_map = warmed.get("qualities_map", {})
                                for q_lbl in ["1080p", "720p", "480p", "360p", "Auto"]:
                                    if q_lbl in q_map:
                                        qualities.append({"quality": q_lbl, "url": f"/api/disha/appx-hls/{q_lbl}.m3u8?token={tok}&q={q_lbl}"})
                            else:
                                embed_player_url = f"/api/disha-player?url={requests.utils.quote(f'{APPX_PLAY_ORIGIN}/combined-img-player?isMobile=true&token={tok}')}"

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

                        # C. Check encrypted_links for HLS m3u8 and quality variants
                        enc_links = data.get("encrypted_links", [])
                        if enc_links and isinstance(enc_links, list):
                            for el in enc_links:
                                q_lbl = str(el.get("title") or el.get("quality") or "Video").strip()
                                first_path = el.get("path") or el.get("backup_url") or el.get("url") or ""
                                if first_path:
                                    dec_stream = decrypt_val(first_path)
                                    if ".m3u8" in dec_stream.lower():
                                        if not hls_stream:
                                            hls_stream = dec_stream
                                        q_url = f"/api/proxy-hls?url={requests.utils.quote(dec_stream)}" if "classx.co.in" in dec_stream else dec_stream
                                        if not any(q["url"] == q_url for q in qualities):
                                            qualities.append({"quality": q_lbl, "url": q_url})

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
                    if d.get("qualities") and isinstance(d.get("qualities"), list) and not qualities:
                        qualities = d.get("qualities")
            except Exception as fb_err:
                debug_collected["gbdoc_fallback_err"] = str(fb_err)

        # Step 4: Client-hinted video ID fallback
        client_vid = request.args.get("vid", "").strip() or request.args.get("v", "").strip()
        if not yt_id and not hls_stream and not embed_player_url and client_vid:
            if ".m3u8" in client_vid.lower():
                hls_stream = client_vid
            elif ("youtube.com" in client_vid or "youtu.be" in client_vid):
                m = re.search(r"(?:v=|\/|embed\/)([0-9A-Za-z_-]{11})", client_vid)
                if m:
                    yt_id = m.group(1)
                    yt_flag = 1
            elif len(client_vid) == 11 and not client_vid.startswith("http"):
                yt_id = client_vid
                yt_flag = 1

        final_hls = hls_stream
        if hls_stream and hls_stream.startswith("http") and ("transcoded-videos.classx.co.in" in hls_stream or "classx.co.in" in hls_stream):
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
            "qualities": qualities,
            "pdf_link": pdf_url,
            "pdf_key": pdf_key,
            "is_pdf_encrypted": is_enc_pdf,
            "has_notes": bool(pdf_url),
            "debug": debug_collected
        }

        # Cache static playable streams (YouTube and unexpiring direct HLS), but never cache expiring Appx tokens permanently
        is_token_stream = "appx-hls" in (final_hls or "") or "token=" in (final_hls or "")
        if yt_id or (final_hls and not is_token_stream and not embed_player_url):
            save_cached_video(effective_id, video_id, res_payload)

        return res_payload

    try:
        coalesce_key = f"video_{effective_id}_{video_id}"
        result = execute_coalesced(coalesce_key, _resolve_video)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": 500, "error": str(e)}), 500
