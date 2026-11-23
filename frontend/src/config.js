// Default to Render production backend proxy; can be overridden via VITE_API_URL
const rawUrl = import.meta.env.VITE_API_URL || 'https://disha-pro-backend.onrender.com/api';
const cleanUrl = rawUrl.replace(/\/+$/, '');
export const API_BASE_URL = cleanUrl.endsWith('/api') ? cleanUrl : `${cleanUrl}/api`;
export const CLOUDFLARE_WORKER_URL = "https://disha-stream.cryvex.workers.dev";
