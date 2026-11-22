import time
import threading
import requests
from config import BASE_URL, CLIENT_SERVICE, AUTH_KEY
from auth_manager import get_candidate_owners_for_course, mark_user_rate_limited, load_session, perform_login

_REQUEST_LOCK = threading.Lock()
_LAST_REQUEST_TIME = 0.0
_REQUEST_COUNTER = 0
MIN_INTERVAL_SECONDS = 0.18  # 180ms delay pacing to prevent Akamai/Appx burst rate limit

# Indian ISP Subnets (Jio, Airtel, Vi, BSNL) for realistic client IP emulation
INDIAN_ISP_SUBNETS = [
    (49, 36),   # Reliance Jio
    (49, 43),   # Reliance Jio
    (106, 215), # Bharti Airtel
    (106, 208), # Bharti Airtel
    (117, 211), # Vodafone Idea
    (152, 58),  # BSNL / MTNL
    (183, 82),  # ACT Fibernet
    (223, 185), # Tata / Hathway
]

def generate_virtual_ip(seed: int) -> str:
    sub = INDIAN_ISP_SUBNETS[seed % len(INDIAN_ISP_SUBNETS)]
    o3 = ((seed * 37) % 250) + 2
    o4 = ((seed * 73) % 250) + 2
    return f"{sub[0]}.{sub[1]}.{o3}.{o4}"

def pace_request():
    global _LAST_REQUEST_TIME, _REQUEST_COUNTER
    with _REQUEST_LOCK:
        _REQUEST_COUNTER += 1
        now = time.time()
        elapsed = now - _LAST_REQUEST_TIME
        if elapsed < MIN_INTERVAL_SECONDS:
            time.sleep(MIN_INTERVAL_SECONDS - elapsed)
        _LAST_REQUEST_TIME = time.time()
        return _REQUEST_COUNTER

def make_disha_request(url, course_id=None, method="GET", data=None, timeout=12):
    """
    Executes a rate-paced, auto-rotated request to Disha/Appx API.
    If course_id is provided, iterates through candidates for that course.
    If 429 or 4002 is detected, marks user and falls back to next candidate.
    """
    if not url.startswith("http"):
        url = f"{BASE_URL}{url.lstrip('/')}"

    # Default to course "default" or "62" when fetching general endpoints (like batches list)
    eff_course_id = course_id or "default"
    candidates = get_candidate_owners_for_course(eff_course_id)
    
    if not candidates:
        sess = load_session()
        if not sess:
            sess = perform_login()
        if sess and sess.get("user_id") and sess.get("token"):
            candidates = [{"userId": sess["user_id"], "token": sess["token"]}]

    if not candidates:
        pool = load_account_pool()
        for k in ["default", "62", "58", "61", "57", "63", "70", "89"]:
            if k in pool and pool[k].get("userId") and pool[k].get("token"):
                candidates.append({"userId": pool[k]["userId"], "token": pool[k]["token"]})
                break

    # Guard against empty candidates to completely eliminate IndexError
    if not candidates:
        candidates = [{}]

    # Try up to 3 candidate accounts
    attempts = max(1, min(len(candidates), 3))
    last_resp = None

    for i in range(attempts):
        cand = candidates[i] if i < len(candidates) else candidates[0]
        token = cand.get("token")
        user_id = cand.get("userId")

        counter = pace_request()
        virtual_ip = generate_virtual_ip(counter)

        headers = {
            "Client-Service": CLIENT_SERVICE,
            "Auth-Key": AUTH_KEY,
            "source": "website",
            "User-Agent": "okhttp/4.9.0",
            "X-Forwarded-For": virtual_ip,
            "X-Real-IP": virtual_ip,
            "CF-Connecting-IP": virtual_ip,
            "True-Client-IP": virtual_ip
        }
        if token:
            headers["Authorization"] = token
        if user_id:
            headers["User-ID"] = str(user_id)

        try:
            if method.upper() == "POST":
                resp = requests.post(url, data=data, headers=headers, timeout=timeout)
            else:
                resp = requests.get(url, headers=headers, timeout=timeout)
            last_resp = resp

            # Check for Rate Limit or 4002
            txt = resp.text.lower() if resp.text else ""
            if resp.status_code == 429 or "too many requests" in txt or "try again after 1 hour" in txt:
                print(f"[!] Rate limit detected for user {user_id} on {url}. Marking cooldown.")
                mark_user_rate_limited(user_id, cooldown_minutes=45)
                continue

            if resp.status_code == 200:
                try:
                    j = resp.json()
                    # Check for Appx 4002 quota limit
                    if j.get("status") == 4002 or "limit reached" in txt:
                        print(f"[!] 4002 Limit reached for user {user_id}. Marking cooldown.")
                        mark_user_rate_limited(user_id, cooldown_minutes=60)
                        continue
                except Exception:
                    pass
                return resp

            # Token expired (401 or 403)
            if resp.status_code in (401, 403):
                cand_email = cand.get("email")
                cand_pwd = cand.get("password")
                owner_key = cand.get("ownerKey")
                if cand_email and cand_pwd:
                    perform_login(email=cand_email, password=cand_pwd, course_key=owner_key)
                else:
                    perform_login()
                continue

        except Exception as e:
            print(f"[!] Request error on attempt {i+1} ({url}): {e}")

    # Return last response or synthetic 503
    if last_resp is not None:
        return last_resp

    synthetic = requests.Response()
    synthetic.status_code = 503
    synthetic._content = b'{"status": 503, "message": "Disha server busy, all candidate accounts exhausted."}'
    return synthetic
