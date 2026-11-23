import base64
import re
from urllib.parse import urlparse
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from config import AES_KEY, DEFAULT_IV, ALLOWED_MEDIA_HOST_SUFFIXES

def get_cipher_decryptor(iv_b64=DEFAULT_IV):
    key = AES_KEY.encode('utf-8')
    iv = base64.b64decode(iv_b64)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    return cipher.decryptor()

def decrypt_val(encrypted_text, iv_b64=DEFAULT_IV):
    if not encrypted_text or not isinstance(encrypted_text, str):
        return encrypted_text or ""
    cipher_b64 = encrypted_text
    active_iv = iv_b64
    if ":" in encrypted_text and not encrypted_text.startswith("http"):
        parts = encrypted_text.split(":", 1)
        cipher_b64, active_iv = parts[0], parts[1]
    try:
        data = base64.b64decode(cipher_b64)
        decryptor = get_cipher_decryptor(active_iv)
        decrypted = decryptor.update(data) + decryptor.finalize()
        pad = decrypted[-1]
        if 1 <= pad <= 16:
            decrypted = decrypted[:-pad]
        return decrypted.decode('utf-8', errors='ignore')
    except Exception:
        return encrypted_text

def extract_pdf_from_raw(raw):
    """Extracts PDF URL, decryption key, and encryption flag from raw Disha API object (gbdoc pattern)"""
    if not isinstance(raw, dict):
        return "", "", False
    is_video = str(raw.get("material_type") or "").upper() == "VIDEO"
    candidates = [
        (raw.get("pdf_link"), raw.get("is_pdf_encrypted"), raw.get("pdf_encryption_key"), "pdf_link"),
        (raw.get("pdf_link2"), raw.get("is_pdf2_encrypted"), raw.get("pdf2_encryption_key"), "pdf_link2"),
        (raw.get("file_link"), raw.get("is_pdf_encrypted"), raw.get("pdf_encryption_key"), "file_link"),
    ]
    pdf_url = ""
    pdf_key = ""
    is_enc = False
    for raw_link, raw_enc_flag, raw_enc_key, field_name in candidates:
        if not raw_link:
            continue
        if is_video and field_name == "file_link":
            continue
        dec = decrypt_val(str(raw_link)) if (":" in str(raw_link) and not str(raw_link).startswith("http")) else str(raw_link).strip()
        if dec and (dec.startswith("http://") or dec.startswith("https://")):
            dec_low = dec.lower()
            if not any(dec_low.endswith(x) for x in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".m3u8", ".mpd", ".mp4", ".ts"]) and "youtube.com" not in dec_low and "youtu.be" not in dec_low:
                pdf_url = dec
                is_enc = str(raw_enc_flag or "0") != "0"
                if is_enc and raw_enc_key:
                    dec_key = decrypt_val(str(raw_enc_key)) if ":" in str(raw_enc_key) else str(raw_enc_key)
                    pdf_key = (dec_key or str(raw_enc_key)).rstrip("\x00")
                break
    return pdf_url, pdf_key, is_enc

def decrypt_xor28_pdf(data: bytes, key_str: str = AES_KEY) -> bytes:
    """If file doesn't start with %PDF, decrypt first 28 bytes via XOR key"""
    if not data or len(data) < 4:
        return data
    # Check if already a valid %PDF
    if data[:4] == b'%PDF':
        return data
    if not key_str:
        return data
        
    out = bytearray(data)
    key_bytes = key_str.encode('utf-8')
    limit = min(28, len(out))
    for i in range(limit):
        mask = key_bytes[i] if i < len(key_bytes) else i
        out[i] = (out[i] ^ mask) & 0xff
    return bytes(out)

def sanitize_pdf_link(raw_link):
    if not raw_link:
        return ""
    dec = decrypt_val(raw_link)
    if not dec or not isinstance(dec, str):
        return ""
    dec = dec.strip()
    if not (dec.startswith("http://") or dec.startswith("https://")):
        return ""
    if dec.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg")):
        return ""
    return dec

def is_allowed_media_url(raw_url: str) -> bool:
    if not raw_url or not isinstance(raw_url, str):
        return False
    if any(c in raw_url for c in ['\r', '\n', '\0']):
        return False
    try:
        parsed = urlparse(raw_url)
        if parsed.scheme not in ('http', 'https'):
            return False
        host = (parsed.hostname or '').lower()
        if host in ('localhost', '0.0.0.0') or host.startswith(('127.', '10.', '192.168.', '169.254.')):
            return False
        return any(host == suffix.lstrip('.') or host.endswith(suffix) for suffix in ALLOWED_MEDIA_HOST_SUFFIXES)
    except Exception:
        return False
