import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'

const api = axios.create({
  baseURL: API_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// Request interceptor: add auth token + request ID
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  const requestId = (typeof crypto !== 'undefined' && crypto.randomUUID) 
    ? crypto.randomUUID() 
    : Math.random().toString(36).substring(2, 15);
  config.headers['X-Request-ID'] = requestId
  console.log(`[API] ${config.method.toUpperCase()} ${config.url}`)
  return config
})

// Response interceptor: handle errors globally
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const requestId = error.response?.data?.request_id
    
    if (status === 401) {
      // Token expired - redirect to login
      localStorage.removeItem('auth_token')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    } else if (status === 429) {
      const retry = error.response.headers?.['retry-after'] || 'unknown'
      console.warn(`[API] Rate limited. Retry after ${retry}s`)
    } else if (status >= 500) {
      console.error(`[API] Server error [${requestId || 'no-req-id'}]:`, error.message)
    }
    
    return Promise.reject(error)
  }
)

export default api
export { API_URL, WS_URL }
