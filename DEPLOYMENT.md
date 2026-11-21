# HRRY DISHA — Production Deployment Guide

## Architecture Overview
```
+---------------------------------------+
|              FRONTEND                 |
|   (React + Vite + Classic Black UI)   |
|   Hosted on: Vercel / Netlify / Local |
+---------------------------------------+
                   │
                   ▼ (Safe REST API)
+---------------------------------------+
|           BACKEND PROXY               |
|      (Flask + Gunicorn + AES Decrypt) |
|      Hosted on: Render / Railway      |
|  * Keeps token & secret keys private  |
+---------------------------------------+
                   │
                   ▼ (Authorized Requests)
+---------------------------------------+
|      Official Disha / AppX API        |
+---------------------------------------+
```

---

## 1. Backend Deployment (Render or Railway)

### Option A: Deploy on Render.com (Free Web Service)
1. GitHub पर एक नया repository बनाएं और `backend/` फोल्डर को पुश करें।
2. [Render Dashboard](https://dashboard.render.com/) पर जाएं -> **New +** -> **Web Service** चुनें।
3. अपना GitHub Repo कनेक्ट करें।
4. Settings:
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT`
5. **Environment Variables** (Settings -> Environment):
   - `DISHA_TOKEN`: आपका JWT टोकन
   - `DISHA_USER_ID`: `1608691`
   - `DISHA_AES_KEY`: `638udh3829162018`
6. Deploy होने के बाद आपको एक URL मिलेगा (उदा. `https://disha-backend.onrender.com`).

### Option B: Deploy on Railway.app
1. [Railway.app](https://railway.app/) पर **New Project** -> **Deploy from GitHub repo** चुनें।
2. `backend` फोल्डर सेलेक्ट करें।
3. Railway स्वचालित रूप से `Procfile` और `requirements.txt` पहचानकर डिप्लॉय कर देगा।

---

## 2. Frontend Deployment (Vercel)

1. [Vercel](https://vercel.com/) पर जाएं -> **Add New Project** -> अपना Repo चुनें।
2. **Root Directory:** `frontend` सेट करें।
3. **Environment Variables:**
   - `VITE_API_URL`: अपने Render/Railway बैकएंड का URL (जैसे `https://disha-backend.onrender.com/api`).
4. **Deploy** पर क्लिक करें। आपका फ्रंटएंड बिना किसी टोकन लीक के 100% सुरक्षित रूप से लाइव हो जाएगा!

---

## 3. Local Development (अभी चालू है)
- **Backend API:** `http://localhost:5000`
- **Frontend App:** `http://localhost:3000`
