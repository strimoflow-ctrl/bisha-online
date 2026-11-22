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
    try:
        data = base64.b64decode(encrypted_text)
        decryptor = get_cipher_decryptor(iv_b64)
        decrypted = decryptor.update(data) + decryptor.finalize()
        pad = decrypted[-1]
        if 1 <= pad <= 16:
            decrypted = decrypted[:-pad]
        return decrypted.decode('utf-8', errors='ignore')
    except Exception:
        return encrypted_text

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
