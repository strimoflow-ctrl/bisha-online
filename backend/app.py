import os
import json
import base64
import re
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

# Load environment variables from .env file
ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(ENV_PATH)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Constants & Configuration from Environment
BASE_URL = os.environ.get("DISHA_BASE_URL", "https://dishaonlineclassesapi.akamai.net.in/")
CLIENT_SERVICE = os.environ.get("DISHA_CLIENT_SERVICE", "Appx")
AUTH_KEY = os.environ.get("DISHA_AUTH_KEY", "appxapi")
AES_KEY = os.environ.get("DISHA_AES_KEY", "638udh3829162018")
DEFAULT_IV = os.environ.get("DISHA_DEFAULT_IV", "ZmVkY2JhOTg3NjU0MzIxMA==")

SESSION_FILE = os.path.join(os.path.dirname(__file__), "session.json")
DISHA_EMAIL = os.environ.get("DISHA_EMAIL") or "hkb4390@gmail.com"
DISHA_PASSWORD = os.environ.get("DISHA_PASSWORD") or "hkb4390"

ACTIVE_SESSION = None

def load_session():
    global ACTIVE_SESSION
    if ACTIVE_SESSION:
        return ACTIVE_SESSION

    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                s = json.load(f)
                if s and s.get("token"):
                    ACTIVE_SESSION = s
                    return ACTIVE_SESSION
        except Exception:
            pass

    token = os.environ.get("DISHA_TOKEN")
    user_id = os.environ.get("DISHA_USER_ID")
    
    if token and user_id:
        ACTIVE_SESSION = {
            "user_id": user_id,
            "token": token,
            "name": os.environ.get("DISHA_USER_NAME", "Disha Pro Student"),
            "phone": os.environ.get("DISHA_USER_PHONE", ""),
            "email": os.environ.get("DISHA_USER_EMAIL", ""),
            "is_paid_user": "1"
        }
        return ACTIVE_SESSION
        
    return None

def perform_login(email=DISHA_EMAIL, password=DISHA_PASSWORD):
    """Auto re-login when session expires"""
    global ACTIVE_SESSION
    url = f"{BASE_URL}post/userLogin"
    data = {"email": email, "password": password}
    headers = {
        "Client-Service": CLIENT_SERVICE,
        "Auth-Key": AUTH_KEY,
        "User-Agent": "okhttp/4.9.0",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    try:
        print(f"[*] Auto-relogging in as {email}...")
        resp = requests.post(url, data=data, headers=headers, timeout=12)
        if resp.status_code == 200:
            res_json = resp.json()
            if res_json.get("status") == 200:
                ud = res_json.get("data", {})
                sess = {
                    "user_id": str(ud.get("userid")),
                    "token": str(ud.get("token")),
                    "name": ud.get("name"),
                    "email": ud.get("email"),
                    "phone": ud.get("phone"),
                    "is_paid_user": ud.get("is_paid_user")
                }
                ACTIVE_SESSION = sess
                os.environ["DISHA_TOKEN"] = sess["token"]
                os.environ["DISHA_USER_ID"] = sess["user_id"]
                try:
                    with open(SESSION_FILE, "w", encoding="utf-8") as f:
                        json.dump(sess, f, indent=2, ensure_ascii=False)
                except Exception:
                    pass
                print("[+] Auto-relogin successful!")
                return sess
    except Exception as e:
        print(f"[!] Auto-login error: {e}")
    return None

def make_disha_request(url, retry=True):
    """Makes request to Disha API and automatically re-logs in if token is expired"""
    headers = get_auth_headers()
    try:
        r = requests.get(url, headers=headers, timeout=12)
        is_401 = False
        if r.status_code == 401:
            is_401 = True
        else:
            try:
                j = r.json()
                if j.get("status") in [401, "401"] or j.get("message") == "Unauthorized.":
                    is_401 = True
            except Exception:
                pass
                
        if is_401 and retry:
            print("[!] Token expired/invalid. Performing auto-relogin...")
            new_sess = perform_login()
            if new_sess:
                headers = get_auth_headers()
                return requests.get(url, headers=headers, timeout=12)
        return r
    except Exception as e:
        raise e

def decrypt_val(cipher_b64: str, iv_b64: str = DEFAULT_IV, key_str: str = AES_KEY) -> str:
    if not cipher_b64 or not isinstance(cipher_b64, str):
        return ""
    try:
        cipher_clean = cipher_b64.strip()
        if ":" in cipher_clean:
            parts = cipher_clean.split(":", 1)
            cipher_clean = parts[0]
            if len(parts) > 1 and parts[1]:
                iv_b64 = parts[1]
                
        ciphertext = base64.b64decode(cipher_clean)
        iv = base64.b64decode(iv_b64)
        key = key_str.encode("utf-8")
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        padded = decryptor.update(ciphertext) + decryptor.finalize()
        pad_len = padded[-1]
        if 1 <= pad_len <= 16:
            return padded[:-pad_len].decode("utf-8")
        return padded.decode("utf-8", errors="ignore")
    except Exception:
        return cipher_b64

def sanitize_pdf_link(raw_link: str) -> str:
    """Decrypts and sanitizes PDF links, filtering out fake/placeholder links"""
    if not raw_link or not isinstance(raw_link, str):
        return ""
    decrypted = decrypt_val(raw_link)
    if not decrypted:
        return ""
    dec_lower = decrypted.lower()
    if "pdflink.com" in dec_lower or not decrypted.startswith("http") or len(decrypted.strip()) < 12:
        return ""
    return decrypted

def get_auth_headers():
    session = load_session()
    headers = {
        "Client-Service": CLIENT_SERVICE,
        "Auth-Key": AUTH_KEY,
        "User-Agent": "okhttp/4.9.0"
    }
    if session:
        tok = str(session.get("token", ""))
        headers["User-ID"] = str(session.get("user_id", ""))
        headers["Authorization"] = tok
        headers["token"] = tok
    return headers

@app.route("/", methods=["GET"])
@app.route("/health", methods=["GET"])
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "online",
        "service": "Disha Pro API Proxy",
        "authenticated": load_session() is not None
    })

@app.route("/api/user", methods=["GET"])
def api_user():
    session = load_session()
    if not session:
        return jsonify({"status": 401, "message": "No session"}), 401
    return jsonify({
        "status": 200,
        "user": {
            "name": "Disha Pro Student",
            "is_paid_user": "1"
        }
    })

@app.route("/api/batches", methods=["GET"])
def api_batches():
    session = load_session()
    if not session:
        session = perform_login()
        if not session:
            return jsonify({"status": 401, "message": "Not authenticated"}), 401
        
    url = f"{BASE_URL}get/mycoursev2"
    try:
        r = make_disha_request(url)
        data = r.json()
        courses = data.get("data", [])
        
        cleaned = []
        for c in courses:
            cleaned.append({
                "id": str(c.get("id")),
                "title": c.get("course_name") or c.get("title") or "दिशा बैच",
                "thumbnail": c.get("course_thumbnail") or c.get("small_course_logo") or "https://appx-content-v2.classx.co.in/subject/2026-03-06-0_8425628023565359.png",
                "expiry": c.get("expiry") or "Lifetime Validity",
                "teacher_name": c.get("teacher_name") or "Disha Teachers Team",
                "is_paid": "1"
            })
            
        return jsonify({"status": 200, "count": len(cleaned), "batches": cleaned})
    except Exception as e:
        return jsonify({"status": 500, "error": str(e)}), 500

@app.route("/api/batch/<course_id>/overview", methods=["GET"])
def api_batch_overview(course_id):
    # 1. Fetch Root Folder info
    root_folder_id = "-1"
    counts = {"videos": "0", "files": "0", "tests": "0"}
    try:
        r_root = make_disha_request(f"{BASE_URL}get/folder_contentsv3?course_id={course_id}&parent_id=-1&start=0")
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
        print(f"Error fetching root folder for {course_id}: {e}")

    # 2. Fetch Live & Upcoming status from official endpoint
    live_classes = []
    upcoming_classes = []
    try:
        status_url = f"{BASE_URL}get/course_contents_by_live_status?course_id={course_id}"
        r_status = make_disha_request(status_url).json()
        status_data = r_status.get("data", {})
        
        if isinstance(status_data, dict):
            # Live now items
            for it in status_data.get("live", []):
                raw_link = it.get("file_link") or it.get("video_id") or it.get("recording_hls") or ""
                vid_id = decrypt_val(raw_link)
                
                is_hls = ".m3u8" in vid_id.lower() or bool(it.get("recording_hls"))
                hls_stream_url = vid_id if ".m3u8" in vid_id.lower() else (it.get("recording_hls") or "")
                yt_id = "" if is_hls else vid_id
                yt_flag = 0 if is_hls else int(it.get("ytFlag", 0) or it.get("ytFlagWeb", 0) or (1 if yt_id else 0))
                
                live_classes.append({
                    "id": str(it.get("id")),
                    "title": it.get("Title") or it.get("title") or "Live Class",
                    "thumbnail": it.get("thumbnail") or "https://appx-content-v2.classx.co.in/subject/2026-11-21-0_540164180995204.png",
                    "video_id": yt_id,
                    "live_status": 1,
                    "date": it.get("date_and_time") or it.get("event_date") or "Live Now",
                    "hls_url": hls_stream_url,
                    "ytFlag": yt_flag,
                    "material_type": "VIDEO"
                })
                
            # Upcoming scheduled items
            for it in status_data.get("upcoming", []):
                upcoming_classes.append({
                    "id": str(it.get("id")),
                    "title": it.get("Title") or it.get("title") or "Upcoming Class",
                    "description": it.get("description") or "",
                    "thumbnail": it.get("thumbnail") or "https://appx-content-v2.classx.co.in/subject/2026-03-06-0_8425628023565359.png",
                    "video_id": "",
                    "live_status": 2, # UPCOMING
                    "date": it.get("date_and_time") or it.get("event_date") or "Starting Soon",
                    "material_type": "VIDEO",
                    "is_upcoming": True
                })
    except Exception as e:
        print(f"Error fetching live status for {course_id}: {e}")

    # 3. Fetch Recent Recorded Lectures (Prioritizing newest content)
    recent_lectures = []
    try:
        if root_folder_id != "-1":
            r_folders = make_disha_request(f"{BASE_URL}get/folder_contentsv3?course_id={course_id}&parent_id={root_folder_id}&start=0").json()
            raw_sub = r_folders.get("data", [])
            # Filter out syllabus folders and sort by folder ID descending for freshest content
            sub_folders = [sf for sf in raw_sub if "syllabus" not in (sf.get("title") or sf.get("Title") or "").lower()]
            sub_folders = sorted(sub_folders, key=lambda x: int(x.get("id", 0) or 0), reverse=True)
            
            for sf in sub_folders:
                if sf.get("material_type") == "FOLDER" and int(sf.get("videos_count", 0)) > 0:
                    r_lecs = make_disha_request(f"{BASE_URL}get/folder_contentsv3?course_id={course_id}&parent_id={sf.get('id')}&start=0").json()
                    raw_items = r_lecs.get("data", [])
                    # Sort items by id descending so newest lectures appear first
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
                                "live_status": 3, # Recorded
                                "pdf_link": clean_pdf,
                                "has_notes": bool(clean_pdf),
                                "date": item.get("date_and_time") or item.get("event_date") or ""
                            })
                            if len(recent_lectures) >= 12:
                                break
                if len(recent_lectures) >= 12:
                    break
    except Exception as e:
        print(f"Error fetching recent lectures for {course_id}: {e}")

    return jsonify({
        "status": 200,
        "root_folder_id": root_folder_id,
        "counts": counts,
        "live_classes": live_classes,
        "upcoming_classes": upcoming_classes,
        "recent_lectures": recent_lectures
    })

@app.route("/api/batch/<course_id>/folders", methods=["GET"])
def api_batch_folders(course_id):
    parent_id = request.args.get("parent_id", "-1")
    
    # If parent_id is -1, resolve directly to root folder so user sees the top-level categories/subjects
    if parent_id == "-1":
        try:
            r_root = make_disha_request(f"{BASE_URL}get/folder_contentsv3?course_id={course_id}&parent_id=-1&start=0").json()
            root_data = r_root.get("data", [])
            if root_data:
                parent_id = str(root_data[0].get("id", "-1"))
        except Exception:
            pass

    # Query without all_content=1 so child folders are preserved hierarchically!
    url = f"{BASE_URL}get/folder_contentsv3?course_id={course_id}&parent_id={parent_id}&start=0"
    
    try:
        r = make_disha_request(url)
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
            
        return jsonify({"status": 200, "count": len(items), "items": items})
    except Exception as e:
        return jsonify({"status": 500, "error": str(e)}), 500

@app.route("/api/batch/<course_id>/video/<video_id>", methods=["GET"])
def api_batch_video_details(course_id, video_id):
    """Dynamically resolves encrypted HLS streams, embedded Appx players, and YouTube IDs for a video"""
    try:
        urls_to_try = [
            f"{BASE_URL}get/fetchVideoDetailsById?course_id={course_id}&video_id={video_id}&ytflag=0&folder_wise_course=1",
            f"{BASE_URL}get/fetchVideoDetailsById?course_id={course_id}&video_id={video_id}&ytflag=1&folder_wise_course=1",
            f"{BASE_URL}get/fetchVideoDetailsById?course_id={course_id}&video_id={video_id}&folder_wise_course=1",
            f"{BASE_URL}get/fetchVideoDetailsById?course_id={course_id}&video_id={video_id}&ytflag=0",
            f"{BASE_URL}get/fetchVideoDetailsById?course_id={course_id}&video_id={video_id}&ytflag=1",
            f"{BASE_URL}get/fetchVideoDetailsById?course_id={course_id}&video_id={video_id}"
        ]
        
        hls_stream = ""
        yt_id = ""
        yt_flag = 0
        embed_player_url = ""
        debug_collected = {}

        for u in urls_to_try:
            try:
                r = make_disha_request(u)
                res_json = r.json()
                data = res_json.get("data", {})
                param_key = u.split("?", 1)[1] if "?" in u else "raw"
                debug_collected[param_key] = data
                
                if isinstance(data, dict):
                    # 1. Check Appx video_player_token for official embedded web player
                    tok = str(data.get("video_player_token") or "").strip()
                    if tok and tok != "1234":
                        base_p = str(data.get("video_player_url") or "")
                        if not base_p or "token=" not in base_p:
                            base_p = "https://appx-play.classx.co.in/combined-img-player?isMobile=true&debug=true&token="
                        full_target = f"{base_p}{tok}"
                        embed_player_url = f"/api/disha-player?url={requests.utils.quote(full_target)}"

                    # 2. Check encrypted_links for HLS m3u8
                    enc_links = data.get("encrypted_links", [])
                    if enc_links and isinstance(enc_links, list):
                        for el in enc_links:
                            first_path = el.get("path") or el.get("backup_url") or el.get("url") or ""
                            if first_path:
                                dec_stream = decrypt_val(first_path)
                                if ".m3u8" in dec_stream.lower() and not hls_stream:
                                    hls_stream = dec_stream

                    # 3. Check direct file_link or video_id
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

                    # 4. Check recording_hls
                    if not hls_stream and data.get("recording_hls"):
                        hls_stream = data.get("recording_hls")
                    
                    # 5. Check clean video_id attribute
                    if not yt_id and not hls_stream and data.get("ytFlag") == 1 and data.get("video_id"):
                        raw_vid = str(data.get("video_id"))
                        dec_vid = decrypt_val(raw_vid)
                        if len(dec_vid) == 11:
                            yt_id = dec_vid
                            yt_flag = 1

                if embed_player_url or hls_stream or yt_id:
                    break
            except Exception as ex:
                debug_collected[u] = str(ex)

        # If stream is from classx CDN requiring referer, route through backend proxy
        final_hls = hls_stream
        if hls_stream and ("transcoded-videos.classx.co.in" in hls_stream or "classx.co.in" in hls_stream):
            final_hls = f"/api/proxy-hls?url={requests.utils.quote(hls_stream)}"

        player_type = "youtube" if yt_id else ("embed" if embed_player_url else ("hls" if final_hls else ""))

        return jsonify({
            "status": 200,
            "video_id": yt_id,
            "hls_url": final_hls,
            "raw_hls_url": hls_stream,
            "embed_player_url": embed_player_url,
            "player_type": player_type,
            "ytFlag": yt_flag,
            "debug": debug_collected
        })
    except Exception as e:
        return jsonify({"status": 500, "error": str(e)}), 500

@app.route("/api/disha-player", methods=["GET"])
def api_disha_player():
    """Proxies Appx protected web player for DRM/encrypted recorded lecture streams"""
    target_url = request.args.get("url")
    if not target_url:
        return "Missing URL", 400
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://player.appx.co.in/"
    }
    
    try:
        r = requests.get(target_url, headers=headers, timeout=15)
        if r.status_code != 200:
            return f"Player Error {r.status_code}", r.status_code
            
        html = r.text
        # Inject base tag so all relative chunks, JS, CSS resolve to Appx CDN cleanly
        if "<head>" in html:
            html = html.replace("<head>", '<head><base href="https://appx-play.classx.co.in/">')
            
        resp = Response(html, status=200, mimetype="text/html")
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["X-Frame-Options"] = "ALLOWALL"
        resp.headers["Content-Security-Policy"] = "frame-ancestors *"
        return resp
    except Exception as e:
        return f"Error loading player: {e}", 500

@app.route("/api/proxy-hls", methods=["GET"])
def proxy_hls():
    """Proxies HLS .m3u8 playlists and .tsc chunks with required Appx Referer headers"""
    target_url = request.args.get("url")
    if not target_url:
        return "Missing URL", 400
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://player.appx.co.in/"
    }
    
    try:
        r = requests.get(target_url, headers=headers, stream=True, timeout=20)
        content_type = r.headers.get("Content-Type", "")
        
        # If it's an m3u8 playlist, rewrite keys and media segments to pass through proxy
        if ".m3u8" in target_url.lower() or "mpegurl" in content_type.lower():
            lines = r.text.splitlines()
            base_url = target_url.rsplit("/", 1)[0] + "/"
            rewritten_lines = []
            
            for line in lines:
                line_str = line.strip()
                if not line_str:
                    continue
                if line_str.startswith("#EXT-X-KEY"):
                    def replace_key_uri(match):
                        raw_uri = match.group(1)
                        full_uri = raw_uri if raw_uri.startswith("http") else base_url + raw_uri
                        proxy_uri = f"/api/proxy-hls?url={requests.utils.quote(full_uri)}"
                        return f'URI="{proxy_uri}"'
                    new_line = re.sub(r'URI="([^"]+)"', replace_key_uri, line_str)
                    rewritten_lines.append(new_line)
                elif line_str.startswith("#"):
                    rewritten_lines.append(line_str)
                else:
                    # Media segment URL
                    full_chunk = line_str if line_str.startswith("http") else base_url + line_str
                    proxy_chunk = f"/api/proxy-hls?url={requests.utils.quote(full_chunk)}"
                    rewritten_lines.append(proxy_chunk)
            
            manifest = "\n".join(rewritten_lines)
            resp = Response(manifest, status=200, mimetype="application/vnd.apple.mpegurl")
            resp.headers["Access-Control-Allow-Origin"] = "*"
            return resp
        else:
            # Video chunk / key data
            def generate():
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        yield chunk
            resp = Response(generate(), status=r.status_code, content_type=content_type or "application/octet-stream")
            resp.headers["Access-Control-Allow-Origin"] = "*"
            resp.headers["Cache-Control"] = "public, max-age=86400"
            return resp
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/check-pdf", methods=["GET"])
def check_pdf():
    """Checks whether a PDF actually exists on the CDN without downloading full file"""
    target_url = request.args.get("url")
    if not target_url or "pdflink.com" in target_url:
        return jsonify({"available": False, "status": 404})
    try:
        resp = requests.head(target_url, headers={"User-Agent": "okhttp/4.9.0"}, timeout=3)
        if resp.status_code == 200:
            return jsonify({"available": True, "status": 200})
        return jsonify({"available": False, "status": resp.status_code})
    except Exception:
        return jsonify({"available": False, "status": 500})

@app.route("/api/proxy-pdf", methods=["GET"])
def proxy_pdf():
    """Proxies and serves PDF cleanly, handling errors gracefully"""
    target_url = request.args.get("url")
    if not target_url or "pdflink.com" in target_url:
        return """
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"><title>PDF सूचना</title>
        <style>body{background:#000;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;padding:20px;text-align:center;}</style>
        </head>
        <body>
        <div>
        <h2 style="color:#f59e0b;margin-bottom:8px;">⚠️ नोट्स उपलब्ध नहीं हैं</h2>
        <p style="color:#a1a1aa;font-size:14px;max-width:420px;line-height:1.6;">इस लेक्चर के लिए शिक्षक द्वारा अभी कोई PDF नोट्स अपलोड नहीं किए गए हैं।</p>
        <button onclick="window.close()" style="margin-top:16px;padding:9px 24px;border-radius:8px;border:none;background:#27272a;color:#fff;font-weight:bold;cursor:pointer;">वापस जाएं</button>
        </div>
        </body>
        </html>
        """, 404

    try:
        resp = requests.get(target_url, headers={"User-Agent": "okhttp/4.9.0"}, stream=True, timeout=12)
        if resp.status_code == 200:
            return Response(resp.iter_content(chunk_size=1024*32), content_type=resp.headers.get("Content-Type", "application/pdf"))
        
        # CDN 404 or Edge Cache error
        return """
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"><title>PDF सूचना</title>
        <style>body{background:#000;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;padding:20px;text-align:center;}</style>
        </head>
        <body>
        <div>
        <h2 style="color:#ef4444;margin-bottom:8px;">⚠️ PDF फाइल सर्वर पर नहीं मिली</h2>
        <p style="color:#a1a1aa;font-size:14px;max-width:420px;line-height:1.6;">यह फाइल दिशा ऑनलाइन क्लासेज के सर्वर पर उपलब्ध नहीं है (Removed or Expired by Disha Server)।</p>
        <button onclick="window.close()" style="margin-top:16px;padding:9px 24px;border-radius:8px;border:none;background:#27272a;color:#fff;font-weight:bold;cursor:pointer;">वापस जाएं</button>
        </div>
        </body>
        </html>
        """, 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"[*] Starting Disha Pro Proxy Backend on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)
