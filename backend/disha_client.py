import time
import threading
import requests
from config import BASE_URL, CLIENT_SERVICE, AUTH_KEY
from auth_manager import get_candidate_owners_for_course, mark_user_rate_limited, load_session, perform_login

_REQUEST_LOCK = threading.Lock()
_LAST_REQUEST_TIME = 0.0
MIN_INTERVAL_SECONDS = 0.18  # 180ms delay pacing to prevent Akamai/Appx burst rate limit

def pace_request():
    global _LAST_REQUEST_TIME
    with _REQUEST_LOCK:
        now = time.time()
        elapsed = now - _LAST_REQUEST_TIME
        if elapsed < MIN_INTERVAL_SECONDS:
            time.sleep(MIN_INTERVAL_SECONDS - elapsed)
        _LAST_REQUEST_TIME = time.time()

def make_disha_request(url, course_id=None, method="GET", data=None, timeout=12):
    """
    Executes a rate-paced, auto-rotated request to Disha/Appx API.
    If course_id is provided, iterates through candidates for that course.
    If 429 or 4002 is detected, marks user and falls back to next candidate.
    """
    if not url.startswith("http"):
        url = f"{BASE_URL}{url.lstrip('/')}"

    candidates = get_candidate_owners_for_course(course_id) if course_id else []
    if not candidates:
        sess = load_session()
        if sess:
            candidates = [{"userId": sess["user_id"], "token": sess["token"]}]

    # Try up to 3 candidate accounts
    attempts = max(1, min(len(candidates), 3))
    last_resp = None

    for i in range(attempts):
        cand = candidates[i] if i < len(candidates) else candidates[0]
        token = cand.get("token")
        user_id = cand.get("userId")

        headers = {
            "Client-Service": CLIENT_SERVICE,
            "Auth-Key": AUTH_KEY,
            "User-Agent": "okhttp/4.9.0"
        }
        if token:
            headers["Authorization"] = token
        if user_id:
            headers["User-ID"] = str(user_id)

        pace_request()

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
