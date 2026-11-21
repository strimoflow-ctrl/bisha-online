const rawUrl = import.meta.env.VITE_API_URL || 'http://localhost:5000/api';
const cleanUrl = rawUrl.replace(/\/+$/, '');
export const API_BASE_URL = cleanUrl.endsWith('/api') ? cleanUrl : `${cleanUrl}/api`;
