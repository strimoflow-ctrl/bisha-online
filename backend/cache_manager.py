import os
import json
import time
import threading
import requests
from config import (
    VIDEO_CACHE_FILE, BATCH_CACHE_FILE, FOLDER_CACHE_FILE,
    FIREBASE_DATABASE_URL, FIREBASE_DATABASE_SECRET
)

# Threading locks for safe concurrency
_CACHE_LOCK = threading.Lock()
_IN_FLIGHT_LOCK = threading.Lock()
IN_FLIGHT_REQUESTS = {}  # {cacheKey: (threading.Event, resultContainer)}

# In-memory stores
MEM_CACHE = {}  # {key: {"data": ..., "expires_at": ...}}

# Load persistent video cache
PERSISTENT_VIDEO_CACHE = {}
if os.path.exists(VIDEO_CACHE_FILE):
    try:
        with open(VIDEO_CACHE_FILE, "r", encoding="utf-8") as f:
            PERSISTENT_VIDEO_CACHE = json.load(f)
    except Exception:
        PERSISTENT_VIDEO_CACHE = {}

# Load persistent batch cache
PERSISTENT_BATCH_CACHE = None
if os.path.exists(BATCH_CACHE_FILE):
    try:
        with open(BATCH_CACHE_FILE, "r", encoding="utf-8") as f:
            PERSISTENT_BATCH_CACHE = json.load(f)
    except Exception:
        PERSISTENT_BATCH_CACHE = None

# Load persistent folder cache
PERSISTENT_FOLDER_CACHE = {}
if os.path.exists(FOLDER_CACHE_FILE):
    try:
        with open(FOLDER_CACHE_FILE, "r", encoding="utf-8") as f:
            PERSISTENT_FOLDER_CACHE = json.load(f)
    except Exception:
        PERSISTENT_FOLDER_CACHE = {}

def get_firebase_url(path: str) -> str:
    clean_path = path.lstrip("/")
    url = f"{FIREBASE_DATABASE_URL}/{clean_path}.json"
    if FIREBASE_DATABASE_SECRET:
        url += f"?auth={FIREBASE_DATABASE_SECRET}"
    return url

# ----------------- Firebase Sync Helpers -----------------
def firebase_get(path: str):
    """Retrieve data from Firebase Realtime Database (REST API)"""
    if not FIREBASE_DATABASE_URL:
        return None
    try:
        u = get_firebase_url(path)
        r = requests.get(u, timeout=4)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[!] Firebase GET error ({path}): {e}")
    return None

def firebase_put(path: str, data):
    """Save data to Firebase Realtime Database asynchronously"""
    if not FIREBASE_DATABASE_URL:
        return
    def _save():
        try:
            u = get_firebase_url(path)
            requests.put(u, json=data, timeout=6)
        except Exception as e:
            print(f"[!] Firebase PUT error ({path}): {e}")
    threading.Thread(target=_save, daemon=True).start()

# ----------------- Batch Cache -----------------
def get_cached_batches():
    global PERSISTENT_BATCH_CACHE
    # 1. Memory check
    if PERSISTENT_BATCH_CACHE:
        return PERSISTENT_BATCH_CACHE
    # 2. Firebase check
    fb_data = firebase_get("disha/batches")
    if fb_data:
        PERSISTENT_BATCH_CACHE = fb_data
        save_cached_batches(fb_data, push_firebase=False)
        return fb_data
    return None

def save_cached_batches(data, push_firebase=True):
    global PERSISTENT_BATCH_CACHE
    with _CACHE_LOCK:
        PERSISTENT_BATCH_CACHE = data
        try:
            with open(BATCH_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    if push_firebase:
        firebase_put("disha/batches", data)

# ----------------- Folder Cache -----------------
def get_cached_folder(course_id: str, parent_id: str):
    key = f"{course_id}_{parent_id}"
    # 1. Memory / local disk
    if key in PERSISTENT_FOLDER_CACHE:
        return PERSISTENT_FOLDER_CACHE[key]
    # 2. Firebase check
    fb_data = firebase_get(f"disha/folders/{key}")
    if fb_data:
        PERSISTENT_FOLDER_CACHE[key] = fb_data
        save_cached_folder(course_id, parent_id, fb_data, push_firebase=False)
        return fb_data
    return None

def save_cached_folder(course_id: str, parent_id: str, data, push_firebase=True):
    key = f"{course_id}_{parent_id}"
    with _CACHE_LOCK:
        PERSISTENT_FOLDER_CACHE[key] = data
        try:
            with open(FOLDER_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(PERSISTENT_FOLDER_CACHE, f, ensure_ascii=False)
        except Exception:
            pass
    if push_firebase:
        firebase_put(f"disha/folders/{key}", data)

# ----------------- Video Details Cache -----------------
def get_cached_video(course_id: str, video_id: str):
    key = f"{course_id}_{video_id}"
    with _CACHE_LOCK:
        return PERSISTENT_VIDEO_CACHE.get(key)

def save_cached_video(course_id: str, video_id: str, data):
    key = f"{course_id}_{video_id}"
    with _CACHE_LOCK:
        PERSISTENT_VIDEO_CACHE[key] = data
        try:
            with open(VIDEO_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(PERSISTENT_VIDEO_CACHE, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

# ----------------- Request Coalescing (Deduplication) -----------------
def execute_coalesced(request_key: str, fetch_fn):
    """
    If multiple clients request the exact same key at the exact same moment,
    only 1 execution runs. All other threads wait and receive the same result.
    """
    with _IN_FLIGHT_LOCK:
        if request_key in IN_FLIGHT_REQUESTS:
            event, result_box = IN_FLIGHT_REQUESTS[request_key]
            is_leader = False
        else:
            event = threading.Event()
            result_box = {"data": None, "error": None}
            IN_FLIGHT_REQUESTS[request_key] = (event, result_box)
            is_leader = True

    if is_leader:
        try:
            res = fetch_fn()
            result_box["data"] = res
        except Exception as e:
            result_box["error"] = e
        finally:
            event.set()
            with _IN_FLIGHT_LOCK:
                IN_FLIGHT_REQUESTS.pop(request_key, None)
        if result_box["error"]:
            raise result_box["error"]
        return result_box["data"]
    else:
        event.wait(timeout=20)
        if result_box["error"]:
            raise result_box["error"]
        return result_box["data"]
