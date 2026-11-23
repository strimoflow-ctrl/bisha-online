from flask import Blueprint, jsonify, request
from config import BASE_URL, SIBLING_COURSE_MAP, BUILTIN_BATCH_CATALOG
from crypto_utils import decrypt_val, sanitize_pdf_link
from disha_client import make_disha_request
from cache_manager import (
    get_cached_batches, save_cached_batches,
    get_cached_folder, save_cached_folder,
    execute_coalesced
)

batches_bp = Blueprint("batches", __name__)

@batches_bp.route("/api/batches", methods=["GET"])
def api_batches():
    # 1. Check Cache / Firebase
    cached = get_cached_batches()
    if cached and cached.get("count", 0) >= len(BUILTIN_BATCH_CATALOG):
        return jsonify(cached)

    def _fetch():
        catalog_list = []
        # Try fetching public courselistnewv2
        try:
            url_all = f"{BASE_URL}get/courselistnewv2?exam_name=&start=-1&userid=0"
            r = make_disha_request(url_all, course_id="default")
            raw_data = r.json().get("data", []) if hasattr(r, 'json') else []
            if isinstance(raw_data, list):
                for b in raw_data:
                    if str(b.get("type", "COURSE")).upper() == "COURSE" and b.get("id"):
                        catalog_list.append({
                            "id": str(b.get("id")),
                            "title": (b.get("course_name") or b.get("name") or "दिशा बैच").strip(),
                            "thumbnail": b.get("course_thumbnail") or b.get("thumbnail") or "https://appx-content-v2.classx.co.in/subject/2026-03-06-0_8425628023565359.png",
                            "expiry": b.get("validity") or "Lifetime Validity",
                            "teacher_name": b.get("teacher_name") or "Disha Teachers Team",
                            "is_paid": "1"
                        })
        except Exception:
            pass

        # Try user's purchased courses
        try:
            url_my = f"{BASE_URL}get/mycoursev2"
            r_my = make_disha_request(url_my, course_id="default")
            my_courses = r_my.json().get("data", []) if hasattr(r_my, 'json') else []
            if isinstance(my_courses, list):
                for b in my_courses:
                    catalog_list.append({
                        "id": str(b.get("id")),
                        "title": (b.get("course_name") or b.get("name") or "दिशा बैच").strip(),
                        "thumbnail": b.get("course_thumbnail") or b.get("thumbnail") or "https://appx-content-v2.classx.co.in/subject/2026-03-06-0_8425628023565359.png",
                        "expiry": b.get("expiry") or b.get("validity") or "Lifetime Validity",
                        "teacher_name": b.get("teacher_name") or "Disha Teachers Team",
                        "is_paid": "1"
                    })
        except Exception:
            pass

        # Format Built-in catalog from all 16 accounts (25 complete batches)
        builtin_formatted = []
        for b in BUILTIN_BATCH_CATALOG:
            builtin_formatted.append({
                "id": str(b.get("id")),
                "title": (b.get("name") or b.get("course_name") or "दिशा बैच").strip(),
                "thumbnail": b.get("thumbnail") or "https://appx-content-v2.classx.co.in/subject/2026-03-06-0_8425628023565359.png",
                "expiry": b.get("validity") or "Lifetime Validity",
                "teacher_name": "Disha Teachers Team",
                "is_paid": "1"
            })

        # Merge and deduplicate by ID
        seen = set()
        merged = []
        for item in catalog_list + builtin_formatted:
            iid = str(item.get("id"))
            if not iid or iid in seen:
                continue
            seen.add(iid)
            merged.append(item)

        res = {"status": 200, "count": len(merged), "batches": merged}
        save_cached_batches(res)
        return res

    try:
        result = execute_coalesced("batches_catalog", _fetch)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": 500, "error": str(e)}), 500

@batches_bp.route("/api/batch/<course_id>/overview", methods=["GET"])
def api_batch_overview(course_id):
    clean_id = str(course_id).split("_")[-1] if "_" in str(course_id) else str(course_id)
    effective_id = SIBLING_COURSE_MAP.get(clean_id, {}).get("hostCourseId", clean_id)

    # 1. Fetch Root Folder info
    root_folder_id = "-1"
    counts = {"videos": "0", "files": "0", "tests": "0"}
    try:
        r_root = make_disha_request(f"{BASE_URL}get/folder_contentsv3?course_id={effective_id}&parent_id=-1&start=0", course_id=effective_id)
        items = r_root.json().get("data", [])
        if items:
            root = items[0]
            root_folder_id = str(root.get("id", "-1"))
            counts = {
                "videos": str(root.get("videos_count", "0")),
                "files": str(root.get("files_count", "0")),
                "tests": str(root.get("tests_count", "0"))
            }
    except Exception as e:
        print(f"Error fetching root folder for {effective_id}: {e}")

    # 2. Fetch Live & Upcoming status
    live_classes = []
    upcoming_classes = []
    try:
        status_url = f"{BASE_URL}get/course_contents_by_live_status?course_id={effective_id}"
        r_status = make_disha_request(status_url, course_id=effective_id).json()
        status_data = r_status.get("data", {})
        
        if isinstance(status_data, dict):
            for it in status_data.get("live", []):
                hls_stream_url = ""
                live_links = it.get("livestream_links", [])
                if live_links and isinstance(live_links, list):
                    first_l = live_links[0].get("path") or ""
                    if first_l:
                        dec_l = decrypt_val(first_l)
                        if ".m3u8" in dec_l.lower():
                            hls_stream_url = dec_l
                            
                raw_link = it.get("file_link") or it.get("video_id") or it.get("recording_hls") or ""
                vid_id = decrypt_val(raw_link) if raw_link else ""
                if not hls_stream_url:
                    if ".m3u8" in vid_id.lower():
                        hls_stream_url = vid_id
                    elif it.get("recording_hls"):
                        hls_stream_url = it.get("recording_hls")
                
                is_hls = bool(hls_stream_url)
                yt_id = "" if is_hls else vid_id
                yt_flag = 0 if is_hls else int(it.get("ytFlag", 0) or it.get("ytFlagWeb", 0) or (1 if yt_id else 0))
                
                live_classes.append({
                    "id": str(it.get("id")),
                    "course_id": str(course_id),
                    "title": it.get("Title") or it.get("title") or "Live Class",
                    "thumbnail": it.get("thumbnail") or "https://appx-content-v2.classx.co.in/subject/2026-11-21-0_540164180995204.png",
                    "video_id": yt_id,
                    "live_status": 1,
                    "date": it.get("date_and_time") or it.get("event_date") or "Live Now",
                    "hls_url": hls_stream_url,
                    "ytFlag": yt_flag,
                    "material_type": "VIDEO"
                })
                
            for it in status_data.get("upcoming", []):
                upcoming_classes.append({
                    "id": str(it.get("id")),
                    "title": it.get("Title") or it.get("title") or "Upcoming Class",
                    "description": it.get("description") or "",
                    "thumbnail": it.get("thumbnail") or "https://appx-content-v2.classx.co.in/subject/2026-03-06-0_8425628023565359.png",
                    "video_id": "",
                    "live_status": 2,
                    "date": it.get("date_and_time") or it.get("event_date") or "Starting Soon",
                    "material_type": "VIDEO",
                    "is_upcoming": True
                })
    except Exception as e:
        print(f"Error fetching live status for {effective_id}: {e}")

    # 3. Fetch Recent Recorded Lectures
    recent_lectures = []
    try:
        if root_folder_id != "-1":
            r_folders = make_disha_request(f"{BASE_URL}get/folder_contentsv3?course_id={effective_id}&parent_id={root_folder_id}&start=0", course_id=effective_id).json()
            raw_sub = r_folders.get("data", [])
            sub_folders = [sf for sf in raw_sub if "syllabus" not in (sf.get("title") or sf.get("Title") or "").lower()]
            sub_folders = sorted(sub_folders, key=lambda x: int(x.get("id", 0) or 0), reverse=True)
            
            for sf in sub_folders:
                if sf.get("material_type") == "FOLDER" and int(sf.get("videos_count", 0)) > 0:
                    r_lecs = make_disha_request(f"{BASE_URL}get/folder_contentsv3?course_id={effective_id}&parent_id={sf.get('id')}&start=0", course_id=effective_id).json()
                    raw_items = r_lecs.get("data", [])
                    sorted_items = sorted(raw_items, key=lambda x: int(x.get("id", 0) or 0), reverse=True)
                    for item in sorted_items:
                        if item.get("material_type") == "VIDEO":
                            dec_id = decrypt_val(item.get("file_link") or item.get("video_id") or "")
                            clean_pdf = sanitize_pdf_link(item.get("pdf_link") or item.get("pdf_link2") or "")
                            
                            recent_lectures.append({
                                "id": str(item.get("id")),
                                "course_id": str(course_id),
                                "title": item.get("Title") or item.get("title") or "Lecture",
                                "thumbnail": item.get("thumbnail") or "https://appx-content-v2.classx.co.in/subject/2026-03-06-0_8425628023565359.png",
                                "video_id": dec_id,
                                "ytFlag": int(item.get("ytFlag", 0) or item.get("ytFlagWeb", 0)),
                                "hls_url": item.get("recording_hls") or "",
                                "material_type": "VIDEO",
                                "live_status": 3,
                                "pdf_link": clean_pdf,
                                "has_notes": bool(clean_pdf),
                                "date": item.get("date_and_time") or item.get("event_date") or ""
                            })
                            if len(recent_lectures) >= 12:
                                break
                if len(recent_lectures) >= 12:
                    break
    except Exception as e:
        print(f"Error fetching recent lectures for {effective_id}: {e}")

    return jsonify({
        "status": 200,
        "root_folder_id": root_folder_id,
        "counts": counts,
        "live_classes": live_classes,
        "upcoming_classes": upcoming_classes,
        "recent_lectures": recent_lectures
    })

@batches_bp.route("/api/batch/<course_id>/folders", methods=["GET"])
def api_batch_folders(course_id):
    parent_id = request.args.get("parent_id", "-1")
    clean_id = str(course_id).split("_")[-1] if "_" in str(course_id) else str(course_id)
    effective_id = SIBLING_COURSE_MAP.get(clean_id, {}).get("hostCourseId", clean_id)

    # Check Sibling Folder Mapping
    if clean_id in SIBLING_COURSE_MAP and parent_id == "-1":
        parent_id = SIBLING_COURSE_MAP[clean_id].get("recordedFolderId", "-1")

    # 1. Check Cache / Firebase
    cached = get_cached_folder(effective_id, parent_id)
    if cached:
        return jsonify(cached)

    def _fetch_folder():
        nonlocal parent_id
        if parent_id == "-1":
            try:
                r_root = make_disha_request(f"{BASE_URL}get/folder_contentsv3?course_id={effective_id}&parent_id=-1&start=0", course_id=effective_id).json()
                root_data = r_root.get("data", [])
                if root_data:
                    parent_id = str(root_data[0].get("id", "-1"))
            except Exception:
                pass

        url = f"{BASE_URL}get/folder_contentsv3?course_id={effective_id}&parent_id={parent_id}&start=0"
        r = make_disha_request(url, course_id=effective_id)
        data = r.json()
        raw_items = data.get("data", [])
        
        items = []
        for it in raw_items:
            mtype = it.get("material_type", "")
            item_id = str(it.get("id", ""))
            title = it.get("Title") or it.get("title") or "Item"
            
            entry = {
                "id": item_id,
                "title": title,
                "material_type": mtype,
                "parent_id": str(it.get("parent_id", "")),
                "thumbnail": it.get("thumbnail") or "",
                "date": it.get("date_and_time") or it.get("event_date") or ""
            }
            
            if mtype == "FOLDER":
                entry["videos_count"] = str(it.get("videos_count", "0"))
                entry["files_count"] = str(it.get("files_count", "0"))
                entry["tests_count"] = str(it.get("tests_count", "0"))
            elif mtype == "VIDEO":
                yt_flag = int(it.get("ytFlag", 0) or it.get("ytFlagWeb", 0))
                raw_file_link = it.get("file_link") or it.get("video_id") or ""
                decrypted_video_id = decrypt_val(raw_file_link) if raw_file_link else ""
                
                hls_stream = it.get("recording_hls") or ""
                if ".m3u8" in decrypted_video_id.lower():
                    hls_stream = decrypted_video_id
                    decrypted_video_id = ""
                    yt_flag = 0
                elif ("youtube.com" in decrypted_video_id or "youtu.be" in decrypted_video_id):
                    m = re.search(r"(?:v=|\/|embed\/)([0-9A-Za-z_-]{11})", decrypted_video_id)
                    if m:
                        decrypted_video_id = m.group(1)
                        yt_flag = 1
                elif len(decrypted_video_id) == 11 and not decrypted_video_id.startswith("http"):
                    yt_flag = 1
                
                clean_pdf = sanitize_pdf_link(it.get("pdf_link") or it.get("pdf_link2") or "")
                live_status = int(it.get("live_status", 3))
                
                entry["ytFlag"] = yt_flag
                entry["video_id"] = decrypted_video_id
                entry["video_player_url"] = it.get("video_player_url") or ""
                entry["hls_url"] = hls_stream
                entry["embed_player_url"] = ""
                entry["course_id"] = str(course_id)
                entry["pdf_link"] = clean_pdf
                entry["has_notes"] = bool(clean_pdf)
                entry["live_status"] = live_status
                entry["is_upcoming"] = (live_status == 2)
                entry["duration"] = it.get("duration") or ""
            elif mtype in ["PDF", "FILE"]:
                clean_pdf = sanitize_pdf_link(it.get("file_link") or it.get("pdf_link") or it.get("pdf_link2") or "")
                entry["pdf_link"] = clean_pdf
                entry["has_file"] = bool(clean_pdf)
            elif mtype == "IMAGE":
                entry["image_url"] = it.get("file_link") or it.get("thumbnail") or ""
            elif mtype == "LINK":
                raw_link = it.get("file_link") or ""
                t_low = title.lower()
                l_low = raw_link.lower()
                if "telegram" in t_low or "telegram" in l_low or "t.me" in l_low:
                    raw_link = "https://t.me/hrbseb10thallcorse"
                elif "whatsapp" in t_low or "whatsapp" in l_low or "chat.whatsapp.com" in l_low:
                    raw_link = "https://whatsapp.com/channel/0029VbF7oDdLo4hdnj39Cw17"
                entry["link_url"] = raw_link
                
            items.append(entry)
            
        # Group items: FOLDERS first, then VIDEOS, then NOTES/PDFs, then others
        def _item_sort_key(it):
            m = it.get("material_type", "")
            if m == "FOLDER":
                return 0
            elif m == "VIDEO":
                return 1
            elif m in ["PDF", "FILE"]:
                return 2
            return 3

        items.sort(key=_item_sort_key)
        res = {"status": 200, "count": len(items), "items": items}
        save_cached_folder(effective_id, parent_id, res)
        return res

    try:
        coalesce_key = f"folder_{effective_id}_{parent_id}"
        result = execute_coalesced(coalesce_key, _fetch_folder)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": 500, "error": str(e)}), 500
