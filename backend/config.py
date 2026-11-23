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

# Cloudflare Edge Streamer (Unlimited Free Bandwidth for HLS Video & PDF Decryption)
CLOUDFLARE_WORKER_URL = os.environ.get("CLOUDFLARE_WORKER_URL", "https://disha-stream.pankajkushwaha20093.workers.dev")

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
    '86': ['62'],
    '63': ['63', '69', '67'],
    '67': ['67', '57'],
    '68': ['67', '57'],
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
    '91': '61',  # 12th Scoring (Hindi & English) Crash Course -> Batch 61
    '68': '67',  # 11th Science -> Batch 67
    '60': '70',  # 12th Commerce -> Batch 70
    '90': '57',  # 12th Commerce Crash Course -> Batch 57 & 70
    '19': '89',  # Spoken English -> Batch 89
    '25': '89',  # 9th Foundation -> Batch 89
    '50': '89',  # Free YouTube Classes -> Batch 89
    '85': '89',  # Disha Foundation Batch -> Batch 89
    '26': '57',  # Basic Math -> Batch 57
    '27': '59',  # English Grammar -> Batch 59
    '65': '87',  # Hindi & Sanskrit Grammar -> Batch 87
    '71': '63',  # 11th Humanities -> Batch 63
}

# Sibling Crash Course mappings (folder redirection for composite batches 86, 88, 91)
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

BUILTIN_BATCH_CATALOG = [
  {
    "id": "91",
    "name": "12th Hindi & English (स्कोरिंग बैच) क्रैश कोर्स -2027",
    "thumbnail": "https://appx-content-v2.classx.co.in/paid_course3/2026-10-09-0_5464053338374512.png",
    "description": "",
    "price": 199,
    "mrp": 251,
    "validity": "12 Months",
    "startDate": "2026-10-09",
    "endDate": "2027-05-30",
    "folderWiseCourse": True
  },
  {
    "id": "90",
    "name": "12th Commerce (मंजिल बैच) क्रैश कोर्स -2027",
    "thumbnail": "https://appx-content-v2.classx.co.in/paid_course3/2026-10-09-0_8369799410571603.png",
    "description": "",
    "price": 399,
    "mrp": 499,
    "validity": "12 Months",
    "startDate": "2026-10-09",
    "endDate": "2027-05-30",
    "folderWiseCourse": True
  },
  {
    "id": "89",
    "name": "12th Arts (मंजिल बैच) क्रैश कोर्स -2027",
    "thumbnail": "https://appx-content-v2.classx.co.in/paid_course3/2026-10-09-0_32339076969925096.png",
    "description": "",
    "price": 399,
    "mrp": 499,
    "validity": "12 Months",
    "startDate": "2026-10-09",
    "endDate": "2027-05-30",
    "folderWiseCourse": True
  },
  {
    "id": "88",
    "name": "12th Science (English Medium) क्रैश कोर्स -2027",
    "thumbnail": "https://appx-content-v2.classx.co.in/paid_course3/2026-10-09-0_9832751891680268.png",
    "description": "",
    "price": 399,
    "mrp": 499,
    "validity": "12 Months",
    "startDate": "2026-10-09",
    "endDate": "2027-05-30",
    "folderWiseCourse": True
  },
  {
    "id": "87",
    "name": "12th Science (हिंदी माध्यम) क्रैश कोर्स -2027",
    "thumbnail": "https://appx-content-v2.classx.co.in/paid_course3/2026-10-09-0_5018466025494253.png",
    "description": "",
    "price": 399,
    "mrp": 499,
    "validity": "12 Months",
    "startDate": "2026-10-09",
    "endDate": "2027-05-30",
    "folderWiseCourse": True
  },
  {
    "id": "86",
    "name": "Dream 450+ (क्रैश कोर्स) -2027",
    "thumbnail": "https://appx-content-v2.classx.co.in/paid_course3/2026-10-09-0_5971931348699795.png",
    "description": "",
    "price": 251,
    "mrp": 299,
    "validity": "12 Months",
    "startDate": "2026-10-09",
    "endDate": "2027-05-30",
    "folderWiseCourse": True
  },
  {
    "id": "85",
    "name": "DISHA FOUNDATION BATCH - 2026",
    "thumbnail": "https://appx-content-v2.classx.co.in/paid_course3/2026-06-15-0_5128795357709232.png",
    "description": "",
    "price": 1000,
    "mrp": 1800,
    "validity": "12 Months",
    "startDate": "2026-06-15",
    "endDate": "2028-07-31",
    "folderWiseCourse": True
  },
  {
    "id": "71",
    "name": "NCERT BOOK ( कक्षा - 9 )",
    "thumbnail": "https://appx-content-v2.classx.co.in/paid_course3/2026-04-22-0_8916661465191855.png",
    "description": "",
    "price": -10,
    "mrp": 10,
    "validity": "12 Months",
    "startDate": "2026-04-22",
    "endDate": "",
    "folderWiseCourse": True
  },
  {
    "id": "67",
    "name": "11th Science - हिंदी माध्यम (2026-2027)",
    "thumbnail": "https://appx-content-v2.classx.co.in/paid_course3/2026-10-09-0_5830879364286718.png",
    "description": "",
    "price": 999,
    "mrp": 1800,
    "validity": "12 Months",
    "startDate": "2026-04-03",
    "endDate": "2027-05-30",
    "folderWiseCourse": True
  },
  {
    "id": "65",
    "name": "Spoken English Batch - 2026",
    "thumbnail": "https://appx-content-v2.classx.co.in/paid_course3/2026-02-27-0_9007380238062749.png",
    "description": "",
    "price": -10,
    "mrp": 399,
    "validity": "12 Months",
    "startDate": "2026-02-27",
    "endDate": "2026-12-31",
    "folderWiseCourse": True
  },
  {
    "id": "63",
    "name": "पहल बैच Class 9th -2027",
    "thumbnail": "https://appx-content-v2.classx.co.in/paid_course3/2026-10-09-0_5202920216546776.png",
    "description": "",
    "price": 399,
    "mrp": 699,
    "validity": "12 Months",
    "startDate": "2026-01-25",
    "endDate": "2027-05-30",
    "folderWiseCourse": True
  },
  {
    "id": "50",
    "name": "Basic Math For All Exam",
    "thumbnail": "https://appx-content-v2.classx.co.in/paid_course3/2025-07-15-0_28774308299138585.png",
    "description": "",
    "price": -10,
    "mrp": 499,
    "validity": "12 Months",
    "startDate": "2025-07-15",
    "endDate": "",
    "folderWiseCourse": True
  },
  {
    "id": "27",
    "name": "NCERT BOOK ( कक्षा - 11 )",
    "thumbnail": "/gb-study-logo.png",
    "description": "",
    "price": -10,
    "mrp": 499,
    "validity": "12 Months",
    "startDate": "2024-07-20",
    "endDate": "2026-07-20",
    "folderWiseCourse": True
  },
  {
    "id": "26",
    "name": "NCERT BOOK ( कक्षा - 12 )",
    "thumbnail": "/gb-study-logo.png",
    "description": "",
    "price": -10,
    "mrp": 10,
    "validity": "12 Months",
    "startDate": "2024-07-19",
    "endDate": "2026-07-19",
    "folderWiseCourse": True
  },
  {
    "id": "25",
    "name": "NCERT BOOK ( कक्षा - 10 )",
    "thumbnail": "https://appxcontent.kaxa.in/paid_course3/2024-07-19-0.054767989830756925.png",
    "description": "",
    "price": -10,
    "mrp": 10,
    "validity": "12 Months",
    "startDate": "2024-07-19",
    "endDate": "2026-07-19",
    "folderWiseCourse": True
  },
  {
    "id": "19",
    "name": "Basic & Spoken English",
    "thumbnail": "https://appxcontent.kaxa.in/paid_course4/2024-02-29-0.20011057585353886.png",
    "description": "",
    "price": -10,
    "mrp": 99,
    "validity": "12 Months",
    "startDate": "2024-02-29",
    "endDate": "2024-08-29",
    "folderWiseCourse": True
  },
  {
    "id": "68",
    "name": "11th Science - English Medium (2026-2027)",
    "thumbnail": "https://appx-content-v2.classx.co.in/paid_course3/2026-10-09-0_5157613393211836.png",
    "description": "",
    "price": 999,
    "mrp": 1800,
    "validity": "12 Months",
    "startDate": "2026-04-03",
    "endDate": "2027-05-30",
    "folderWiseCourse": True
  },
  {
    "id": "69",
    "name": "11th Arts - परिवर्तन बैच (2026-2027)",
    "thumbnail": "https://appx-content-v2.classx.co.in/paid_course3/2026-10-09-0_45840549607422265.png",
    "description": "",
    "price": 999,
    "mrp": 1800,
    "validity": "12 Months",
    "startDate": "2026-04-03",
    "endDate": "2027-05-30",
    "folderWiseCourse": True
  },
  {
    "id": "70",
    "name": "11th Commerce - परिवर्तन बैच (2026-2027)",
    "thumbnail": "https://appx-content-v2.classx.co.in/paid_course3/2026-10-09-0_7449872659522191.png",
    "description": "",
    "price": 999,
    "mrp": 1800,
    "validity": "12 Months",
    "startDate": "2026-04-03",
    "endDate": "2027-05-30",
    "folderWiseCourse": True
  },
  {
    "id": "62",
    "name": "DREAM 450+ ( 2026 - 27 )",
    "thumbnail": "https://appx-content-v2.classx.co.in/paid_course3/2026-10-09-0_40395267525579726.png",
    "description": "",
    "price": 499,
    "mrp": 999,
    "validity": "12 Months",
    "startDate": "2026-01-25",
    "endDate": "2027-05-30",
    "folderWiseCourse": True
  },
  {
    "id": "57",
    "name": "12th Science - हिंदी माध्यम (2026-2027)",
    "thumbnail": "https://appx-content-v2.classx.co.in/paid_course3/2026-10-09-0_5421602312915103.png",
    "description": "",
    "price": 999,
    "mrp": 2400,
    "validity": "12 Months",
    "startDate": "2026-01-18",
    "endDate": "2027-05-30",
    "folderWiseCourse": True
  },
  {
    "id": "58",
    "name": "12th Science - English Medium (2026-2027)",
    "thumbnail": "https://appx-content-v2.classx.co.in/paid_course3/2026-10-09-0_8889059753324439.png",
    "description": "",
    "price": 999,
    "mrp": 2400,
    "validity": "12 Months",
    "startDate": "2026-01-18",
    "endDate": "2027-05-30",
    "folderWiseCourse": True
  },
  {
    "id": "59",
    "name": "12th Arts मंजिल (Full बैच)-2026 -27",
    "thumbnail": "https://appx-content-v2.classx.co.in/paid_course3/2026-10-09-0_4275590058146138.png",
    "description": "",
    "price": 999,
    "mrp": 2400,
    "validity": "12 Months",
    "startDate": "2026-01-18",
    "endDate": "2027-05-30",
    "folderWiseCourse": True
  },
  {
    "id": "60",
    "name": "12th Commerce मंजिल (Full बैच)-2026 -27",
    "thumbnail": "https://appx-content-v2.classx.co.in/paid_course3/2026-10-09-0_7357466332402398.png",
    "description": "",
    "price": 999,
    "mrp": 2400,
    "validity": "12 Months",
    "startDate": "2026-01-18",
    "endDate": "2027-05-30",
    "folderWiseCourse": True
  },
  {
    "id": "61",
    "name": "12th स्कोरिंग (Hindi & English Full बैच)  - 2026 - 27",
    "thumbnail": "https://appx-content-v2.classx.co.in/paid_course3/2026-10-09-0_9524113671132266.png",
    "description": "",
    "price": 499,
    "mrp": 799,
    "validity": "12 Months",
    "startDate": "2026-01-18",
    "endDate": "2027-05-30",
    "folderWiseCourse": True
  }
]
