import os
import json
from dotenv import load_dotenv

# Load environment variables
ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(ENV_PATH)

# Base Disha & Appx API configuration
BASE_URL = os.environ.get("DISHA_BASE_URL", "https://dishaonlineclassesapi.akamai.net.in/")
CLIENT_SERVICE = os.environ.get("DISHA_CLIENT_SERVICE", "Appx")
AUTH_KEY = os.environ.get("DISHA_AUTH_KEY", "appxapi")
AES_KEY = os.environ.get("DISHA_AES_KEY", "638udh3829162018")
DEFAULT_IV = os.environ.get("DISHA_DEFAULT_IV", "ZmVkY2JhOTg3NjU0MzIxMA==")

# Account & Credentials Configuration
DISHA_EMAIL = os.environ.get("DISHA_EMAIL", "hkb4390@gmail.com")
DISHA_PASSWORD = os.environ.get("DISHA_PASSWORD", "hkb4390")
SESSION_FILE = os.path.join(os.path.dirname(__file__), "session.json")
ACCOUNT_POOL_FILE = os.path.join(os.path.dirname(__file__), "account_pool.json")
DISHA_ACCOUNT_POOL_ENV = os.environ.get("DISHA_ACCOUNT_POOL", "")

# Server Port
PORT = int(os.environ.get("PORT", 5000))

# Firebase Integration (Optional - REST API mode for 0 dependency requirements)
FIREBASE_DATABASE_URL = os.environ.get("FIREBASE_DATABASE_URL", "").rstrip("/")
FIREBASE_DATABASE_SECRET = os.environ.get("FIREBASE_DATABASE_SECRET", "")

# Cache Paths
CACHE_DIR = os.path.join(os.path.dirname(__file__), "data_cache")
os.makedirs(CACHE_DIR, exist_ok=True)
VIDEO_CACHE_FILE = os.path.join(CACHE_DIR, "video_cache.json")
BATCH_CACHE_FILE = os.path.join(CACHE_DIR, "batch_cache.json")
FOLDER_CACHE_FILE = os.path.join(CACHE_DIR, "folder_cache.json")

# Course Owners Pool Map (Which accounts have purchased which batches)
COURSE_OWNERS_POOL_MAP = {
    '87': ['87', '57'],
    '57': ['57', '87'],
    '58': ['58'],
    '88': ['58'],
    '59': ['59', '89', '61'],
    '89': ['89', '59', '61'],
    '61': ['61', '89', '59'],
    '91': ['61', '89', '59'],
    '62': ['62'],
    '86': ['62', '86'],
    '63': ['63', '69', '67'],
    '67': ['67', '57'],
    '68': ['67', '57', '68'],
    '69': ['69'],
    '70': ['70', '57'],
    '60': ['70', '57'],
    '90': ['57', '70'],
    '65': ['87', '57', '58', '89', '61', '63', '67', '69', '70'],
    '26': ['57', '58', '59', '89', '61', '67', '69'],
    '27': ['59', '89', '67', '69'],
    '71': ['63', '67', '69'],
    '25': ['89'],
    '19': ['89', '67'],
    '50': ['89', '69'],
    '85': ['89', '69'],
}

# Redirect crash courses to their verified parent courses
VERIFIED_COURSE_OWNER_REDIRECT = {
    '86': '62',  # 10th Crash Course 2027 -> owned by Batch 62
    '88': '58',  # 12th Science English Crash Course -> Batch 58
    '91': '61',  # 12th Arts English Crash Course -> Batch 61
    '68': '67',  # 11th Science -> Batch 67
    '60': '70',  # 12th Commerce -> Batch 70
    '90': '57',  # 12th Commerce Crash Course -> Batch 57 & 70
    '19': '89',  # Spoken English -> Batch 89
    '25': '89',  # 9th Foundation -> Batch 89
    '50': '89',  # Free YouTube Classes -> Batch 89
    '85': '89',  # Simultaneous/Navodaya -> Batch 89
    '26': '57',  # Basic Math
    '27': '59',  # English Grammar
    '65': '87',  # Hindi & Sanskrit Grammar
    '71': '63',  # 11th Humanities
}

# Sibling Crash Course mappings (folder redirection)
SIBLING_COURSE_MAP = {
    "86": {
        "hostCourseId": "62",
        "crashFolderId": "160503",
        "recordedFolderId": "116616",
        "infoFolderId": "131911",
    },
    "88": {
        "hostCourseId": "58",
        "crashFolderId": "160507",
        "recordedFolderId": "110993",
        "infoFolderId": "122949",
    },
    "91": {
        "hostCourseId": "61",
        "crashFolderId": "160504",
        "recordedFolderId": "109187",
        "infoFolderId": "122962",
    },
}

ALLOWED_MEDIA_HOST_SUFFIXES = [
    '.classx.co.in',
    '.appx.co.in',
    '.kaxa.in',
    '.cloudfront.net',
    '.cloud-front.in',
    '.teachx.in',
    '.akamaihd.net',
    '.akamai.net.in',
    '.googlevideo.com',
    '.ytimg.com',
    '.youtube.com',
    '.youtu.be',
]
