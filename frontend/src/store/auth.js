import { create } from 'zustand'
import api from '../api/client'

export const useAuthStore = create((set, get) => ({
  user: null,
  token: localStorage.getItem('auth_token') || null,
  loading: false,
  error: null,

  async login(username, password) {
    set({ loading: true, error: null })
    try {
      const { data } = await api.post('/api/auth/login', { username, password })
      localStorage.setItem('auth_token', data.access_token)
      set({ user: data.user, token: data.access_token, loading: false })
      return true
    } catch (e) {
      set({ error: e.response?.data?.detail || e.response?.data?.error || 'Login failed', loading: false })
      return false
    }
  },

  logout() {
    localStorage.removeItem('auth_token')
    set({ user: null, token: null })
  },

  isAuthenticated() {
    return !!get().token
  },
}))
