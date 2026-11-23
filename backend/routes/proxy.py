import re
import json
import base64
import requests
from urllib.parse import urlparse, urljoin, quote, unquote
from flask import Blueprint, Response, request, jsonify
from crypto_utils import decrypt_xor28_pdf, is_allowed_media_url
from .shim_data import SHIM_TEMPLATE
from appx_hls import (
    warm_and_extract_appx_token, 
    decode_appx_segment_text, 
    decode_appx_segment_binary, 
    unscramble_appx_ts
)
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

import time

proxy_bp = Blueprint("proxy", __name__)

BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
APPX_PLAY_ORIGIN = "https://appx-play.classx.co.in"

# Cache for rendered player HTML so single-use Appx video_player_token is never consumed twice
APPX_PLAYER_HTML_CACHE = {}  # { clean_target: (html, expire_time) }

def build_native_appx_player_shim(base_url: str, pathname_and_query: str) -> str:
    """
    Client-side shim injected into the Appx player HTML.
    Intercepts window.fetch and XMLHttpRequest to redirect classx.co.in media requests
    through our backend /api/mp/* proxy, eliminating CORS & missing Referer blocks.
    """
    safe_base = base_url.replace('"', '&quot;')
    safe_path = json.dumps(pathname_and_query)
    return SHIM_TEMPLATE.replace("__SAFE_BASE_SLOT__", safe_base).replace("__SAFE_PATH_SLOT__", safe_path)

@proxy_bp.route("/uhs-hls-player/<path:subpath>", methods=["GET", "OPTIONS"])
def proxy_uhs_player(subpath):
    """Proxies player scripts, worker scripts, and decryption assets for Appx DRM player"""
    if request.method == "OPTIONS":
        resp = Response(status=200)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "*"
        return resp

    target = f"https://appx-play.classx.co.in/uhs-hls-player/{subpath}"
    if request.query_string:
        target += f"?{request.query_string.decode('utf-8', errors='ignore')}"
    headers = {
        "User-Agent": BROWSER_UA,
        "Referer": "https://player.appx.co.in/"
    }
    try:
        r = requests.get(target, headers=headers, timeout=15)
        content_type = r.headers.get("Content-Type")
        if not content_type:
            if subpath.endswith(".js"):
                content_type = "application/javascript"
            elif subpath.endswith(".css"):
                content_type = "text/css"
            elif subpath.endswith(".png"):
                content_type = "image/png"
            elif subpath.endswith((".jpg", ".jpeg")):
                content_type = "image/jpeg"
            else:
                content_type = "application/octet-stream"

        resp = Response(r.content, status=r.status_code, mimetype=content_type)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp
    except Exception as e:
        return f"Proxy error: {e}", 502

@proxy_bp.route("/no-poster.jpg", methods=["GET"])
def proxy_no_poster():
    """Proxies default poster image for Appx video player"""
    target = "https://appx-play.classx.co.in/no-poster.jpg"
    headers = {"User-Agent": BROWSER_UA, "Referer": "https://player.appx.co.in/"}
    try:
        r = requests.get(target, headers=headers, timeout=10)
        resp = Response(r.content, status=r.status_code, mimetype="image/jpeg")
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp
    except Exception:
        return "", 204

@proxy_bp.route("/_next/<path:subpath>", methods=["GET", "OPTIONS"])
def proxy_next_static(subpath):
    """Proxies Next.js chunks, CSS, and polyfills for the Appx embedded player"""
    if request.method == "OPTIONS":
        resp = Response(status=200)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "*"
        return resp

    target = f"https://appx-play.classx.co.in/_next/{subpath}"
    if request.query_string:
        target += f"?{request.query_string.decode('utf-8', errors='ignore')}"
    headers = {
        "User-Agent": BROWSER_UA,
        "Referer": "https://player.appx.co.in/"
    }
    try:
        r = requests.get(target, headers=headers, timeout=15)
        content_type = r.headers.get("Content-Type")
        body = r.content

        if subpath.endswith(".js"):
            content_type = "application/javascript"
            try:
                text = r.text
                if "!n.has(e)" in text:
                    text = text.replace("!n.has(e)", '(n.set(e,"watermark"),false)')
                    body = text.encode("utf-8")
            except Exception:
                pass
        elif subpath.endswith(".css"):
            content_type = "text/css"
        elif not content_type:
            content_type = "application/octet-stream"

        resp = Response(body, status=r.status_code, mimetype=content_type)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp
    except Exception as e:
        return f"Proxy error: {e}", 502

def _render_disha_player(target_url: str):
    """Internal helper to fetch and inject shim into Appx web player"""
    parsed = urlparse(target_url)
    clean_target = target_url.replace("&debug=true", "").replace("?debug=true&", "?").replace("?debug=true", "")
    pathname_and_query = parsed.path + ("?" + parsed.query if parsed.query else "")

    now = time.time()
    # 1. Return cached HTML so single-use token is never consumed multiple times by player workers
    cached_entry = APPX_PLAYER_HTML_CACHE.get(clean_target)
    if cached_entry:
        cached_html, exp = cached_entry
        if exp > now:
            resp = Response(cached_html, status=200, mimetype="text/html; charset=utf-8")
            resp.headers["Access-Control-Allow-Origin"] = "*"
            resp.headers["X-Frame-Options"] = "ALLOWALL"
            resp.headers["Content-Security-Policy"] = "frame-ancestors *"
            return resp

    headers = {
        "User-Agent": BROWSER_UA,
        "Referer": "https://dishaonlineclasses.classx.co.in/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    try:
        r = requests.get(clean_target, headers=headers, timeout=15)
        if r.status_code != 200:
            if cached_entry:
                resp = Response(cached_entry[0], status=200, mimetype="text/html; charset=utf-8")
                resp.headers["Access-Control-Allow-Origin"] = "*"
                return resp
            return f"Player Error {r.status_code}", r.status_code

        html = r.text
        # Strip existing base tags if any
        html = re.sub(r'<base\s+[^>]*>', '', html, flags=re.IGNORECASE)
        # Strip crossorigin attributes from preload and inline scripts
        html = re.sub(r'\s+crossorigin(?:=(?:"[^"]*"|\'[^\']*\'|[^\s>]+))?', '', html, flags=re.IGNORECASE)
        html = re.sub(r',\s*["\']crossOrigin["\']\s*:\s*["\']anonymous["\']', '', html)

        # Inject native shim and watermark style
        shim = build_native_appx_player_shim(clean_target, pathname_and_query)
        watermark_style = '<style>#lovable-badge,[aria-label*="COMBINED_IMG_PLAYER"],nextjs-portal,div[data-nextjs-dialog-overlay],#next-route-announcer{display:none!important}#watermark{opacity:0.01!important;font-size:1px!important;pointer-events:none!important}</style>'

        if '<head>' in html:
            html = html.replace('<head>', f'<head>{shim}{watermark_style}')
        else:
            html = f"{shim}{watermark_style}{html}"

        # Cache only when HTML contains valid stream metadata and not expired
        if "Token Expired" not in html and ("__next_f" in html or "kstr" in html or "uhs" in html):
            APPX_PLAYER_HTML_CACHE[clean_target] = (html, now + 7200)

        resp = Response(html, status=200, mimetype="text/html; charset=utf-8")
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["X-Frame-Options"] = "ALLOWALL"
        resp.headers["Content-Security-Policy"] = "frame-ancestors *"
        return resp
    except Exception as e:
        if cached_entry:
            resp = Response(cached_entry[0], status=200, mimetype="text/html; charset=utf-8")
            resp.headers["Access-Control-Allow-Origin"] = "*"
            return resp
        return f"Error loading player: {e}", 500

@proxy_bp.route("/combined-img-player", methods=["GET"])
def proxy_combined_img_player():
    """Direct route for /combined-img-player so Next.js matches document path and avoids cross-origin redirects"""
    query_str = request.query_string.decode("utf-8", errors="ignore")
    full_target = "https://appx-play.classx.co.in/combined-img-player"
    if query_str:
        full_target += f"?{query_str}"
    return _render_disha_player(full_target)

@proxy_bp.route("/api/disha-player", methods=["GET"])
def api_disha_player():
    """Proxies Appx protected web player and injects native CORS shim and media proxy hooks"""
    target_url = request.args.get("url")
    if not target_url:
        return "Missing URL", 400
    return _render_disha_player(target_url)

@proxy_bp.route("/api/mp/<path:subpath>", methods=["GET", "POST", "OPTIONS"])
def proxy_media_segment(subpath):
    """
    Reverse proxy for Appx video manifests (.m3u8), keys, and media segments (.ts/.m4s).
    Ensures player fetches pass without CORS or Referer rejection from ClassX CDNs.
    """
    if request.method == "OPTIONS":
        resp = Response(status=200)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "*"
        return resp

    parts = subpath.split('/')
    b64_part = parts[0] if parts else ''
    if not b64_part:
        return "Missing segment token", 400

    try:
        # Restore URL-safe base64 padding
        padded_b64 = b64_part.replace('-', '+').replace('_', '/')
        padded_b64 += '=' * (-len(padded_b64) % 4)
        decoded_url = base64.b64decode(padded_b64).decode('utf-8').strip()
    except Exception as e:
        return f"Invalid segment token: {e}", 400

    if not is_allowed_media_url(decoded_url):
        return "Forbidden media host", 403

    # If relative subpath resolved against decodedUrl
    if len(parts) >= 2:
        try:
            rel_subpath = '/'.join(parts[1:])
            orig_filename = decoded_url.split('?')[0].split('/')[-1]
            if len(parts) > 2 or (rel_subpath and rel_subpath != orig_filename and rel_subpath != 'f' and rel_subpath != 'seg'):
                resolved = urljoin(decoded_url, rel_subpath)
                if is_allowed_media_url(resolved):
                    decoded_url = resolved
        except Exception:
            pass

    is_classx_cdn = bool(re.search(r'transcoded-videos|liveclasses\.cloud-front\.in|pull-dq\.classx\.co\.in', decoded_url, re.IGNORECASE))
    fetch_headers = {
        "User-Agent": BROWSER_UA,
        "Origin": "https://dishaonlineclasses.classx.co.in" if is_classx_cdn else APPX_PLAY_ORIGIN,
        "Referer": "https://dishaonlineclasses.classx.co.in/" if is_classx_cdn else f"{APPX_PLAY_ORIGIN}/",
        "Accept": request.headers.get("Accept", "*/*")
    }
    if request.headers.get("Range"):
        fetch_headers["Range"] = request.headers.get("Range")

    try:
        up_res = requests.get(decoded_url, headers=fetch_headers, stream=True, timeout=20)
        ct = up_res.headers.get("Content-Type", "")

        # If it's an m3u8 playlist, rewrite child segments to also route through /api/mp/
        if ".m3u8" in decoded_url.lower() or "mpegurl" in ct.lower():
            m3u8_text = up_res.text
            base_parsed = urlparse(decoded_url)

            def encode_child_mp_url(raw_child):
                raw_child = raw_child.strip()
                if not raw_child or raw_child.startswith('#'):
                    return raw_child
                try:
                    full_href = urljoin(decoded_url, raw_child)
                    if not is_allowed_media_url(full_href):
                        return raw_child
                    b64_str = base64.b64encode(full_href.encode('utf-8')).decode('utf-8').replace('+', '-').replace('/', '_').rstrip('=')
                    name = full_href.split('?')[0].split('/')[-1] or 'seg'
                    return f"/api/mp/{b64_str}/{quote(name)}"
                except Exception:
                    return raw_child

            rewritten_lines = []
            for line in m3u8_text.splitlines():
                t = line.strip()
                if not t:
                    rewritten_lines.append(line)
                    continue
                if t.startswith('#EXT-X-KEY'):
                    def replace_key(m):
                        orig_uri = m.group(1)
                        new_uri = encode_child_mp_url(orig_uri)
                        return f'URI="{new_uri}"'
                    rewritten_lines.append(re.sub(r'URI="([^"]+)"', replace_key, t))
                elif t.startswith('#'):
                    rewritten_lines.append(t)
                else:
                    rewritten_lines.append(encode_child_mp_url(t))

            resp = Response('\n'.join(rewritten_lines), status=up_res.status_code, mimetype="application/vnd.apple.mpegurl; charset=utf-8")
            resp.headers["Access-Control-Allow-Origin"] = "*"
            return resp

        # Direct media segment or key
        def generate():
            for chunk in up_res.iter_content(chunk_size=65536):
                if chunk:
                    yield chunk

        resp = Response(generate(), status=up_res.status_code, content_type=ct or "application/octet-stream")
        resp.headers["Access-Control-Allow-Origin"] = "*"
        if up_res.headers.get("Content-Range"):
            resp.headers["Content-Range"] = up_res.headers.get("Content-Range")
        return resp
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@proxy_bp.route("/api/proxy-hls", methods=["GET"])
def proxy_hls():
    """Proxies direct HLS .m3u8 playlists and .tsc chunks with required Appx Referer headers"""
    target_url = request.args.get("url")
    if not target_url:
        return "Missing URL", 400

    headers = {
        "User-Agent": BROWSER_UA,
        "Referer": "https://player.appx.co.in/"
    }

    try:
        r = requests.get(target_url, headers=headers, stream=True, timeout=20)
        content_type = r.headers.get("Content-Type", "")

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
                    full_chunk = line_str if line_str.startswith("http") else base_url + line_str
                    proxy_chunk = f"/api/proxy-hls?url={requests.utils.quote(full_chunk)}"
                    rewritten_lines.append(proxy_chunk)

            manifest = "\n".join(rewritten_lines)
            resp = Response(manifest, status=200, mimetype="application/vnd.apple.mpegurl")
            resp.headers["Access-Control-Allow-Origin"] = "*"
            return resp
        else:
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

@proxy_bp.route("/api/check-pdf", methods=["GET"])
def check_pdf():
    """Checks whether a PDF actually exists on the CDN without downloading full file"""
    target_url = request.args.get("url") or request.args.get("u")
    if not target_url or "pdflink.com" in target_url:
        return jsonify({"available": False, "status": 404})
    headers = {
        "User-Agent": BROWSER_UA,
        "Referer": "https://dishaonlineclasses.classx.co.in/",
        "Accept": "*/*"
    }
    try:
        resp = requests.head(target_url, headers=headers, timeout=5)
        if resp.status_code == 200:
            return jsonify({"available": True, "status": 200})
        # If HEAD not allowed by CDN, try GET with range 0-10
        r_get = requests.get(target_url, headers={**headers, "Range": "bytes=0-10"}, timeout=5)
        if r_get.status_code in (200, 206):
            return jsonify({"available": True, "status": 200})
        return jsonify({"available": True, "status": 200})
    except Exception:
        # Default to available so frontend can attempt direct proxy download
        return jsonify({"available": True, "status": 200})

@proxy_bp.route("/api/proxy-pdf", methods=["GET"])
@proxy_bp.route("/api/disha/pdf-file", methods=["GET"])
def proxy_pdf():
    """Proxies and serves PDF cleanly, repairing XOR-28 encrypted headers when needed"""
    target_url = request.args.get("url") or request.args.get("u")
    xor_key = request.args.get("k") or request.args.get("key") or ""
    download_flag = request.args.get("download") == "1"
    filename = request.args.get("filename") or "disha-class-notes.pdf"
    if not filename.endswith(".pdf"):
        filename += ".pdf"

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

    headers = {
        "User-Agent": BROWSER_UA,
        "Referer": "https://dishaonlineclasses.classx.co.in/",
        "Accept": "*/*"
    }
    try:
        resp = requests.get(target_url, headers=headers, timeout=25)
        if resp.status_code == 200:
            data = resp.content
            # Decrypt XOR-28 if not raw %PDF
            if xor_key and data[:4] != b'%PDF':
                data = decrypt_xor28_pdf(data, xor_key)
            elif data[:4] != b'%PDF':
                from config import AES_KEY
                data = decrypt_xor28_pdf(data, AES_KEY)

            disposition = f'attachment; filename="{filename}"' if download_flag else f'inline; filename="{filename}"'
            r = Response(data, status=200, mimetype="application/pdf")
            r.headers["Access-Control-Allow-Origin"] = "*"
            r.headers["Content-Disposition"] = disposition
            r.headers["Cache-Control"] = "public, max-age=86400"
            return r

        return f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"><title>PDF सूचना</title>
        <style>body{background:#000;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;padding:20px;text-align:center;}</style>
        </head>
        <body>
        <div>
        <h2 style="color:#ef4444;margin-bottom:8px;">⚠️ PDF फाइल सर्वर पर नहीं मिली</h2>
        <p style="color:#a1a1aa;font-size:14px;max-width:420px;line-height:1.6;">यह फाइल दिशा ऑनलाइन क्लासेज के सर्वर पर उपलब्ध नहीं है (HTTP {resp.status_code})।</p>
        <button onclick="window.close()" style="margin-top:16px;padding:9px 24px;border-radius:8px;border:none;background:#27272a;color:#fff;font-weight:bold;cursor:pointer;">वापस जाएं</button>
        </div>
        </body>
        </html>
        """, 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================================
# Native Appx Decrypted HLS Manifest & Stream Endpoints (Pure HTML5 Video)
# ============================================================================
@proxy_bp.route("/api/disha/appx-hls", methods=["GET"])
@proxy_bp.route("/api/disha/appx-hls/<name>", methods=["GET"])
def api_disha_appx_hls(name=None):
    token = request.args.get("token", "").strip()
    requested_q = request.args.get("q", "").strip()
    if not token:
        return "Missing stream token", 400

    entry = warm_and_extract_appx_token(token)
    if not entry:
        return "Stream token expired or unavailable", 404

    active_variant = (requested_q and entry.get("qualities_map", {}).get(requested_q)) or {
        "hls_key": entry["hls_key"],
        "m3u8_text": entry["m3u8_text"]
    }

    # Extract active_key as 32-char hex string and uhs_version
    key_hex = active_variant["hls_key"].hex()
    uhs_version = float(entry.get("uhs_version", 3.0) or 3.0)

    lines = active_variant["m3u8_text"].splitlines()
    out_lines = []
    media_sequence = 0
    current_iv_hex = ""
    seg_idx = 0
    has_end_list = False
    q_param = f"&q={quote(requested_q)}" if requested_q else ""

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("#EXT-X-MEDIA-SEQUENCE:"):
            m = re.search(r"#EXT-X-MEDIA-SEQUENCE:(\d+)", line, re.IGNORECASE)
            if m:
                media_sequence = int(m.group(1))
            out_lines.append(line)
            continue

        if line.startswith("#EXT-X-KEY:"):
            m = re.search(r"IV=0x([0-9a-fA-F]{32})", line, re.IGNORECASE)
            if m:
                current_iv_hex = m.group(1).lower()
            # Omit #EXT-X-KEY because /api/disha/appx-seg delivers fully decrypted MPEG-TS
            continue

        if line == "#EXT-X-ENDLIST":
            has_end_list = True
            out_lines.append(line)
            continue

        if line.startswith("http://") or line.startswith("https://"):
            iv_for_seg = current_iv_hex or f"{media_sequence + seg_idx:032x}"
            idx_now = seg_idx
            seg_idx += 1
            # Pass key_hex and uhs_version directly for 100% stateless multi-worker decryption
            out_lines.append(f"/api/disha/appx-seg/seg-{idx_now}.ts?k={key_hex}&iv={iv_for_seg}&v={uhs_version}&u={quote(line)}")
            continue

        out_lines.append(line)

    if not has_end_list:
        out_lines.append("#EXT-X-ENDLIST")

    resp = Response("\n".join(out_lines) + "\n", status=200, mimetype="application/vnd.apple.mpegurl")
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Cache-Control"] = "no-store"
    return resp

@proxy_bp.route("/api/disha/appx-seg", methods=["GET"])
@proxy_bp.route("/api/disha/appx-seg/<name>", methods=["GET"])
def api_disha_appx_seg(name=None):
    key_hex = request.args.get("k", "").strip()
    token = request.args.get("t", "").strip()
    requested_q = request.args.get("q", "").strip()
    iv_hex = request.args.get("iv", "").strip()
    seg_url = request.args.get("u", "").strip()

    try:
        uhs_v = float(request.args.get("v", 3.0) or 3.0)
    except Exception:
        uhs_v = 3.0

    if not seg_url:
        return "Invalid segment parameters", 400

    # Primary: stateless key passed in URL (works across all Gunicorn workers without shared cache)
    if key_hex and len(key_hex) == 32:
        try:
            active_key = bytes.fromhex(key_hex)
        except Exception:
            return "Invalid key hex", 400
    elif token:
        entry = warm_and_extract_appx_token(token)
        if not entry:
            return "Token session not found", 404
        active_key = (requested_q and entry.get("qualities_map", {}).get(requested_q, {}).get("hls_key")) or entry["hls_key"]
        uhs_v = float(entry.get("uhs_version", 3.0) or 3.0)
    else:
        return "Missing key or token", 400

    hls_iv = bytes.fromhex(iv_hex) if (iv_hex and len(iv_hex) == 32) else (b"\x00" * 16)

    m_ext = re.search(r"(\.ts[a-z]?)(?:\?|$)", seg_url, re.IGNORECASE)
    ext = m_ext.group(1).lower() if m_ext else ".tsd"

    seg_headers = {
        "User-Agent": BROWSER_UA,
        "Origin": APPX_PLAY_ORIGIN,
        "Referer": f"{APPX_PLAY_ORIGIN}/"
    }

    try:
        r = None
        for attempt in range(2):
            try:
                r = requests.get(seg_url, headers=seg_headers, timeout=20)
                if r.status_code == 200:
                    break
            except Exception:
                if attempt == 1:
                    raise
                time.sleep(0.3)

        if not r or r.status_code != 200:
            status_code = r.status_code if r else 502
            return f"Upstream segment HTTP {status_code}", status_code

        # Layer 1: Decode wrapper (.tse, .tsa, .tsd, .tsf, etc.)
        if ext == ".ts":
            enc_bytes = r.content
        elif ext in [".tsf", ".tsg", ".tsh", ".tsi", ".tsj"]:
            enc_bytes = decode_appx_segment_binary(r.content, ext)
        else:
            enc_bytes = decode_appx_segment_text(r.content, ext)

        # Layer 2: AES-128-CBC Decrypt
        rem = len(enc_bytes) % 16
        if rem != 0:
            enc_bytes = enc_bytes[:len(enc_bytes) - rem]

        if not enc_bytes:
            return "Empty segment payload", 500

        cipher = Cipher(algorithms.AES(active_key), modes.CBC(hls_iv), backend=default_backend())
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(enc_bytes) + decryptor.finalize()

        # Layer 3: Unscramble Appx PES payload bitwise NOT and PTS XOR timestamps
        clean_ts = unscramble_appx_ts(decrypted, uhs_v)

        resp = Response(clean_ts, status=200, mimetype="video/mp2t")
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Cache-Control"] = "public, max-age=3600"
        return resp
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Segment decrypt error: {e}", 500
