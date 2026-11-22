import re
import requests
from flask import Blueprint, Response, request, jsonify
from crypto_utils import decrypt_xor28_pdf, is_allowed_media_url

proxy_bp = Blueprint("proxy", __name__)

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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
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
            else:
                content_type = "application/octet-stream"

        resp = Response(r.content, status=r.status_code, mimetype=content_type)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp
    except Exception as e:
        return f"Proxy error: {e}", 502

@proxy_bp.route("/api/disha-player", methods=["GET"])
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
        resp = Response(html, status=200, mimetype="text/html")
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["X-Frame-Options"] = "ALLOWALL"
        resp.headers["Content-Security-Policy"] = "frame-ancestors *"
        return resp
    except Exception as e:
        return f"Error loading player: {e}", 500

@proxy_bp.route("/api/proxy-hls", methods=["GET"])
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

@proxy_bp.route("/api/proxy-pdf", methods=["GET"])
def proxy_pdf():
    """Proxies and serves PDF cleanly, repairing XOR-28 encrypted headers when needed"""
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
        resp = requests.get(target_url, headers={"User-Agent": "okhttp/4.9.0"}, timeout=20)
        if resp.status_code == 200:
            pdf_bytes = decrypt_xor28_pdf(resp.content)
            r = Response(pdf_bytes, status=200, mimetype="application/pdf")
            r.headers["Access-Control-Allow-Origin"] = "*"
            r.headers["Content-Disposition"] = "inline; filename=lecture_notes.pdf"
            return r
        
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
