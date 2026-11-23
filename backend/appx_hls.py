import re
import json
import time
import base64
import hashlib
import requests
from urllib.parse import urlparse, quote, unquote
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding

BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
APPX_PLAY_ORIGIN = "https://appx-play.classx.co.in"

# In-memory vault for decrypted Appx streams { token: entry }
APPX_TOKEN_VAULT = {}

def derive_appx_player_key(datetime_str: str, inner_token: str) -> bytes:
    last4 = datetime_str[-4:]
    start_idx = int(last4[0])
    end_idx = int(last4[1:3])
    mode_digit = last4[3]
    seed = (datetime_str + inner_token[start_idx:end_idx]).encode("utf-8")
    h = hashlib.sha256(seed).digest()
    if mode_digit == "6":
        return h[:16]
    if mode_digit == "7":
        return h[:24]
    return h

def decrypt_appx_payload(cipher_b64: str, key_bytes: bytes, iv_b64: str, mode_digit: str) -> str:
    iv = base64.b64decode(iv_b64)
    encrypted = base64.b64decode(cipher_b64)
    cipher = Cipher(algorithms.AES(key_bytes), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded_data = decryptor.update(encrypted) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    decrypted = unpadder.update(padded_data) + unpadder.finalize()
    return decrypted.decode("utf-8", errors="ignore")

def lenient_b64decode(b64_data) -> bytes:
    if isinstance(b64_data, str):
        b64_bytes = b64_data.encode('ascii', errors='ignore')
    else:
        b64_bytes = bytes(b64_data)
    clean = re.sub(rb'[^A-Za-z0-9+/]', b'', b64_bytes)
    missing = len(clean) % 4
    if missing:
        clean += b'=' * (4 - missing)
    try:
        return base64.b64decode(clean)
    except Exception:
        return base64.b64decode(clean + b'===', validate=False)

def decode_appx_segment_text(raw_input, ext: str) -> bytes:
    clean_ext = ext.lower()
    if isinstance(raw_input, (bytes, bytearray)):
        text = raw_input.decode('utf-8', errors='ignore')
    else:
        text = str(raw_input)

    if clean_ext == ".tsa":
        b64 = bytes(((ord(c) - 20) & 0xFF) for c in text)
        return lenient_b64decode(b64)
    if clean_ext == ".tsb":
        b64 = bytes((((ord(c) >> 3) ^ 42) & 0xFF) for c in text)
        return lenient_b64decode(b64)
    if clean_ext == ".tsc":
        b64 = bytes(((ord(c) - 10) & 0xFF) for c in text)
        return lenient_b64decode(b64)
    if clean_ext == ".tsd":
        b64 = bytes(((ord(c) >> 2) & 0xFF) for c in text)
        return lenient_b64decode(b64)
    if clean_ext == ".tse":
        b64 = bytes((((ord(c) ^ 42) >> 3) & 0xFF) for c in text)
        return lenient_b64decode(b64)
    return lenient_b64decode(text.encode('utf-8', errors='ignore'))

def decode_appx_segment_binary(input_bytes: bytes, ext: str) -> bytes:
    clean_ext = ext.lower()
    out = bytearray(input_bytes)
    if clean_ext == ".tsf":
        for i in range(len(out)):
            out[i] = (out[i] ^ 10) & 0xFF
        return bytes(out)
    if clean_ext == ".tsg":
        for i in range(len(out)):
            out[i] = (~out[i]) & 0xFF
        return bytes(out)
    if clean_ext == ".tsh":
        for i in range(0, len(out) - 1, 2):
            out[i], out[i + 1] = out[i + 1], out[i]
        return bytes(out)
    if clean_ext == ".tsi":
        for i in range(len(out)):
            out[i] = (out[i] ^ 0xAA) & 0xFF
        return bytes(out)
    if clean_ext == ".tsj":
        for i in range(len(out)):
            out[i] = (out[i] - 42) & 0xFF
        return bytes(out)
    return bytes(out)

def read_mpeg_ts_pts(buf: bytearray, offset: int) -> int:
    return (
        (buf[offset + 0] & 0x0E) * 536870912 +
        (buf[offset + 1] & 0xFF) * 4194304 +
        (buf[offset + 2] & 0xFE) * 16384 +
        (buf[offset + 3] & 0xFF) * 128 +
        (buf[offset + 4] & 0xFE) // 2
    )

def write_mpeg_ts_pts(buf: bytearray, offset: int, pts: int, marker_bits: int):
    hi3 = (pts // 0x40000000) & 0x07
    low30 = pts & 0x3FFFFFFF
    buf[offset + 0] = ((marker_bits & 0x0F) << 4) | (hi3 << 1) | 1
    buf[offset + 1] = (low30 >> 22) & 0xFF
    buf[offset + 2] = (((low30 >> 15) & 0x7F) << 1) | 1
    buf[offset + 3] = (low30 >> 7) & 0xFF
    buf[offset + 4] = ((low30 & 0x7F) << 1) | 1

def unscramble_appx_ts(input_bytes: bytes, uhs_version: float = 3.0) -> bytes:
    buf = bytearray(input_bytes)
    pmt_pid = -1
    pid_short_start = set()

    for start in range(0, len(buf) - 187, 188):
        if buf[start] != 0x47:
            continue
        stt = bool(buf[start + 1] & 0x40)
        pid = ((buf[start + 1] & 0x1F) << 8) | buf[start + 2]
        atf = (buf[start + 3] & 0x30) >> 4
        offset = start + 5 + buf[start + 4] if atf > 1 else start + 4
        if offset >= start + 188:
            continue

        if pid == 0:
            psi_offset = offset + buf[offset] + 1 if stt else offset
            if psi_offset + 11 < start + 188:
                pmt_pid = ((buf[psi_offset + 10] & 0x1F) << 8) | buf[psi_offset + 11]
            continue

        if pid == pmt_pid or pid == 0x11 or pid == 0x1FFF:
            continue

        payload_len = start + 188 - offset
        if stt:
            pid_short_start.discard(pid)
            if payload_len < 19:
                pid_short_start.add(pid)

        if uhs_version >= 3 and payload_len == 184:
            if not stt and pid in pid_short_start:
                pid_short_start.discard(pid)
            else:
                for j in range(94):
                    buf[offset + j] = (~buf[offset + j]) & 0xFF

        if stt and offset + 14 <= start + 188:
            pes_prefix = (buf[offset] << 16) | (buf[offset + 1] << 8) | buf[offset + 2]
            if pes_prefix == 1:
                pes_flags = buf[offset + 7]
                if pes_flags & 0x80:
                    pts = read_mpeg_ts_pts(buf, offset + 9)
                    has_dts = bool(pes_flags & 0x40) and offset + 19 <= start + 188
                    dts = read_mpeg_ts_pts(buf, offset + 14) if has_dts else pts
                    if pts > 100000000 or dts > 100000000:
                        pts = ((pts ^ 0xFF674FF) & 0xFFFFFFFF) * 4
                        dts = ((dts ^ 0xFF674FF) & 0xFFFFFFFF) * 4
                        write_mpeg_ts_pts(buf, offset + 9, pts, 0x03 if has_dts else 0x02)
                        if has_dts:
                            write_mpeg_ts_pts(buf, offset + 14, dts, 0x01)
    return bytes(buf)

def warm_and_extract_appx_token(player_token: str):
    clean_token = str(player_token or "").strip()
    if not clean_token or clean_token == "1234":
        return None

    now = time.time()
    existing = APPX_TOKEN_VAULT.get(clean_token)
    if existing and existing.get("expires_at", 0) > now:
        return existing

    try:
        final_url = f"{APPX_PLAY_ORIGIN}/combined-img-player?isMobile=true&token={quote(clean_token)}"
        headers = {
            "User-Agent": BROWSER_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://dishaonlineclasses.classx.co.in/"
        }
        r = requests.get(final_url, headers=headers, timeout=12)
        if r.status_code != 200:
            return None

        raw_html = r.text
        if "Token Expired" in raw_html or '"kstr":""' in raw_html or r'\"kstr\":\"\"' in raw_html:
            return None

        kstr = ""
        jstr = ""
        datetime_str = ""
        ivb6 = ""
        inner_token = clean_token
        uhs_version = 3.0
        full_rsc = ""

        # Extract from __NEXT_DATA__
        m_nd = re.search(r'<script id="__NEXT_DATA__" type="application\/json">([\s\S]*?)<\/script>', raw_html)
        if m_nd:
            try:
                nd = json.loads(m_nd.group(1))
                pp = nd.get("props", {}).get("pageProps", {})
                kstr = str(pp.get("kstr") or "")
                jstr = str(pp.get("jstr") or "")
                datetime_str = str(pp.get("datetime") or "")
                ivb6 = str(pp.get("ivb6") or "")
                if pp.get("token"):
                    inner_token = str(pp.get("token"))
                if pp.get("details"):
                    det = json.loads(pp.get("details")) if isinstance(pp.get("details"), str) else pp.get("details")
                    if det.get("uhs_version"):
                        uhs_version = float(det.get("uhs_version"))
            except Exception:
                pass

        # Extract from self.__next_f RSC chunks
        for m_rsc in re.finditer(r'self\.__next_f\.push\(\[1,"([\s\S]*?)"\]\)', raw_html):
            try:
                full_rsc += json.loads(f'"{m_rsc.group(1)}"')
            except Exception:
                pass

        if full_rsc:
            if not kstr:
                m = re.search(r'"kstr":"([^"]+)"', full_rsc)
                if m: kstr = m.group(1)
            if not jstr:
                m = re.search(r'"jstr":"([^"]+)"', full_rsc)
                if m: jstr = m.group(1)
            if not datetime_str:
                m = re.search(r'"datetime":"([^"]+)"', full_rsc)
                if m: datetime_str = m.group(1)
            if not ivb6:
                m = re.search(r'"ivb6":"([^"]+)"', full_rsc)
                if m: ivb6 = m.group(1)
            m_uhs = re.search(r'uhs_version\\?":\\?"([0-9.]+)', full_rsc, re.IGNORECASE)
            if m_uhs:
                try: uhs_version = float(m_uhs.group(1))
                except Exception: pass

        if not kstr or not jstr or not datetime_str or not ivb6:
            return None

        mode_digit = datetime_str[-1]
        key_buf = derive_appx_player_key(datetime_str, inner_token)
        hls_key_b64 = decrypt_appx_payload(kstr, key_buf, ivb6, mode_digit)
        m3u8_text = decrypt_appx_payload(jstr, key_buf, ivb6, mode_digit)
        hls_key = base64.b64decode(hls_key_b64)

        if not m3u8_text or "#EXTM3U" not in m3u8_text or len(hls_key) != 16:
            return None

        qualities_map = {}
        if full_rsc:
            for qm in re.finditer(r'"quality":"([^"]+)"[^}]*?"kstr":"([^"]+)","jstr":"([^"]+)"', full_rsc):
                q_label = qm.group(1).strip()
                q_kstr = qm.group(2).strip()
                q_jstr = qm.group(3).strip()
                if not q_label or not q_kstr or not q_jstr or q_label in qualities_map:
                    continue
                try:
                    q_key_b64 = decrypt_appx_payload(q_kstr, key_buf, ivb6, mode_digit)
                    q_m3u8 = decrypt_appx_payload(q_jstr, key_buf, ivb6, mode_digit)
                    q_key = base64.b64decode(q_key_b64)
                    if q_m3u8 and "#EXTM3U" in q_m3u8 and len(q_key) == 16:
                        qualities_map[q_label] = {"hls_key": q_key, "m3u8_text": q_m3u8}
                except Exception:
                    pass

        default_quality = qualities_map.get("720p") or qualities_map.get("480p") or qualities_map.get("360p") or {
            "hls_key": hls_key,
            "m3u8_text": m3u8_text
        }

        entry = {
            "token": clean_token,
            "hls_key": default_quality["hls_key"],
            "m3u8_text": default_quality["m3u8_text"],
            "uhs_version": uhs_version,
            "qualities_map": qualities_map,
            "expires_at": now + 7200
        }
        APPX_TOKEN_VAULT[clean_token] = entry
        return entry
    except Exception as e:
        return None
