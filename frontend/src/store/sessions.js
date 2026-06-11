import { create } from 'zustand'
import api from '../api/client'

export const useSessionsStore = create((set, get) => ({
  sessions: [],
  selectedId: null,
  currentSession: null,
  loading: false,
  stats: null,

  async fetchSessions() {
    set({ loading: true })
    try {
      const { data } = await api.get('/api/dataset/list?limit=100')
      set({ sessions: data, loading: false })
    } catch (e) {
      set({ loading: false })
    }
  },

  async fetchStats() {
    try {
      const { data } = await api.get('/api/dataset/stats')
      set({ stats: data })
    } catch (e) {}
  },

  async selectSession(id) {
    set({ selectedId: id, currentSession: null })
    try {
      const { data } = await api.get(`/api/dataset/${id}`)
      set({ currentSession: data })
    } catch (e) {
      console.error('Failed to load session:', e)
    }
  },

  async updateLabel(id, label) {
    try {
      await api.patch(`/api/dataset/${id}/label`, { label })
      set((state) => ({
        sessions: state.sessions.map(s => 
          s.session_id === id ? { ...s, action_label: label } : s
        ),
        currentSession: state.currentSession?.session_id === id
          ? { ...state.currentSession, action_label: label }
          : state.currentSession,
      }))
    } catch (e) {
      console.error('Label update failed:', e)
    }
  },

  async deleteSession(id) {
    try {
      await api.delete(`/api/dataset/${id}`)
      set((state) => ({
        sessions: state.sessions.filter(s => s.session_id !== id),
        selectedId: state.selectedId === id ? null : state.selectedId,
        currentSession: state.currentSession?.session_id === id ? null : state.currentSession,
      }))
    } catch (e) {
      console.error('Delete failed:', e)
    }
  },

  addSession(session) {
    set((state) => ({
      sessions: [session, ...state.sessions],
    }))
  },
}))
