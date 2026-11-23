import os
import json
import time
import requests
from config import (
    BASE_URL, CLIENT_SERVICE, AUTH_KEY,
    DISHA_EMAIL, DISHA_PASSWORD,
    SESSION_FILE, ACCOUNT_POOL_FILE, DISHA_ACCOUNT_POOL_ENV,
    COURSE_OWNERS_POOL_MAP, VERIFIED_COURSE_OWNER_REDIRECT, SIBLING_COURSE_MAP
)

ACTIVE_SESSION = None
ACCOUNT_POOL = {}
RATE_LIMITED_USERS = {}  # {userId: blocked_until_timestamp}

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

def perform_login(email=None, password=None, course_key=None):
    """Auto re-login when session or pool token expires"""
    global ACTIVE_SESSION, ACCOUNT_POOL
    email = email or DISHA_EMAIL
    password = password or DISHA_PASSWORD
    if not email or not password:
        return None

    url = f"{BASE_URL}post/userLogin"
    data = {"email": email, "password": password}
    headers = {
        "Client-Service": CLIENT_SERVICE,
        "Auth-Key": AUTH_KEY,
        "User-Agent": "okhttp/4.9.0",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    try:
        print(f"[*] Auto-logging in as {email} for batch {course_key or 'default'}...")
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
                
                # Update specific account in pool if course_key provided
                if course_key and course_key in ACCOUNT_POOL:
                    ACCOUNT_POOL[course_key]["token"] = sess["token"]
                    ACCOUNT_POOL[course_key]["userId"] = sess["user_id"]

                # If primary account, update ACTIVE_SESSION and session.json
                if email == DISHA_EMAIL:
                    ACTIVE_SESSION = sess
                    os.environ["DISHA_TOKEN"] = sess["token"]
                    os.environ["DISHA_USER_ID"] = sess["user_id"]
                    try:
                        with open(SESSION_FILE, "w", encoding="utf-8") as f:
                            json.dump(sess, f, indent=2, ensure_ascii=False)
                    except Exception:
                        pass
                print(f"[+] Login successful for {email} (User {sess['user_id']})!")
                return sess
    except Exception as e:
        print(f"[!] Auto-login error for {email}: {e}")
    return None

def load_account_pool():
    global ACCOUNT_POOL
    if ACCOUNT_POOL:
        return ACCOUNT_POOL

    # 1. From Environment Variable (Preferred for Cloud & Security)
    if DISHA_ACCOUNT_POOL_ENV:
        try:
            pool = json.loads(DISHA_ACCOUNT_POOL_ENV)
            if isinstance(pool, dict) and pool:
                ACCOUNT_POOL = pool
                print(f"[+] Loaded {len(ACCOUNT_POOL)} accounts from DISHA_ACCOUNT_POOL env var.")
                return ACCOUNT_POOL
        except Exception as e:
            print(f"[!] Failed to parse DISHA_ACCOUNT_POOL from env: {e}")

    # 2. From local file account_pool.json
    if os.path.exists(ACCOUNT_POOL_FILE):
        try:
            with open(ACCOUNT_POOL_FILE, "r", encoding="utf-8") as f:
                pool = json.load(f)
                if isinstance(pool, dict) and pool:
                    ACCOUNT_POOL = pool
                    print(f"[+] Loaded {len(ACCOUNT_POOL)} accounts from {ACCOUNT_POOL_FILE}.")
                    return ACCOUNT_POOL
        except Exception as e:
            print(f"[!] Failed to load {ACCOUNT_POOL_FILE}: {e}")

    # 3. Fallback to active session
    sess = load_session()
    if sess:
        ACCOUNT_POOL = {
            "default": {"userId": sess["user_id"], "token": sess["token"]},
            "62": {"userId": sess["user_id"], "token": sess["token"]}
        }
    return ACCOUNT_POOL

def mark_user_rate_limited(user_id: str, cooldown_minutes: int = 3):
    """Puts a user account in brief cooldown (3 mins) when it encounters 429 or quota limit"""
    if not user_id:
        return
    RATE_LIMITED_USERS[str(user_id)] = time.time() + (cooldown_minutes * 60)
    print(f"[!] Marked user {user_id} as rate-limited for {cooldown_minutes} minutes.")

def clear_rate_limits():
    """Clears all rate limit cooldowns"""
    global RATE_LIMITED_USERS
    RATE_LIMITED_USERS.clear()

def get_candidate_owners_for_course(course_id: str) -> list:
    """Returns candidate (userId, token) pairs for a course, prioritizing non-rate-limited accounts"""
    pool = load_account_pool()
    clean_id = str(course_id or "").strip()
    clean_id = clean_id.split("_")[-1] if "_" in clean_id else clean_id
    effective_id = SIBLING_COURSE_MAP.get(clean_id, {}).get("hostCourseId", clean_id)

    keys = (
        COURSE_OWNERS_POOL_MAP.get(clean_id) or
        COURSE_OWNERS_POOL_MAP.get(effective_id) or
        [VERIFIED_COURSE_OWNER_REDIRECT.get(clean_id, clean_id), clean_id]
    )

    now = time.time()
    available = []
    cooldown = []
    seen_users = set()

    for k in keys:
        cred = pool.get(k)
        if cred and cred.get("userId") and cred.get("token"):
            uid = str(cred["userId"])
            if uid in seen_users:
                continue
            seen_users.add(uid)
            blocked_until = RATE_LIMITED_USERS.get(uid, 0)
            candidate = {
                "userId": uid,
                "token": str(cred["token"]),
                "email": cred.get("email"),
                "password": cred.get("password"),
                "ownerKey": k
            }
            if blocked_until > now:
                cooldown.append(candidate)
            else:
                available.append(candidate)

    # Always ensure default/session account is available as final fallback
    def_cred = pool.get("default")
    if def_cred and def_cred.get("userId") and str(def_cred["userId"]) not in seen_users:
        uid = str(def_cred["userId"])
        candidate = {
            "userId": uid,
            "token": str(def_cred["token"]),
            "email": def_cred.get("email"),
            "password": def_cred.get("password"),
            "ownerKey": "default"
        }
        if RATE_LIMITED_USERS.get(uid, 0) > now:
            cooldown.append(candidate)
        else:
            available.append(candidate)

    return available + cooldown
