import { create } from 'zustand'
import api from '../api/client'

export const useMotionStore = create((set, get) => ({
  sessions: [],
  selectedSession: null,
  frames: [],
  currentFrame: 0,
  playing: false,
  loading: false,
  error: null,

  fetchSessions: async () => {
    set({ loading: true, error: null })
    try {
      const { data } = await api.get('/api/sessions')
      const mapped = data.map(s => ({
        ...s,
        session_id: s.id,
        duration_sec: s.duration_s,
        status: 'ready'
      }))
      set({ sessions: mapped })
    } catch (err) {
      set({ error: 'Failed to load sessions list' })
    } finally {
      set({ loading: false })
    }
  },

  selectSession: async (sessionId) => {
    if (!sessionId) {
      set({ selectedSession: null, frames: [], currentFrame: 0, playing: false })
      return
    }
    set({ loading: true, error: null })
    try {
      const { data: sessionData } = await api.get(`/api/sessions/${sessionId}`)
      const session = {
        ...sessionData,
        session_id: sessionData.id,
        duration_sec: sessionData.duration_s,
        status: 'ready'
      }

      const { data: frames } = await api.get(`/api/sessions/${sessionId}/frames?limit=1000`)

      set({
        selectedSession: session,
        frames: frames,
        currentFrame: 0,
        playing: false,
      })
    } catch (err) {
      set({ error: 'Failed to load session coordinate frames' })
    } finally {
      set({ loading: false })
    }
  },

  deleteSession: async (sessionId) => {
    try {
      await api.delete(`/api/sessions/${sessionId}`)
      const sessions = get().sessions.filter(s => s.session_id !== sessionId)
      set({ sessions })
      if (get().selectedSession?.session_id === sessionId) {
        set({ selectedSession: null, frames: [], currentFrame: 0 })
      }
    } catch (err) {
      set({ error: 'Failed to delete session' })
    }
  },

  setFrame: (frame) => {
    const total = get().frames.length
    if (total === 0) return
    
    let nextFrame = frame
    if (typeof frame === 'function') {
      nextFrame = frame(get().currentFrame)
    }
    
    if (nextFrame >= total) {
      set({ currentFrame: 0 })
    } else if (nextFrame < 0) {
      set({ currentFrame: total - 1 })
    } else {
      set({ currentFrame: nextFrame })
    }
  },

  togglePlay: () => {
    set({ playing: !get().playing })
  },

  setPlaying: (playing) => {
    set({ playing })
  },

  updateLabel: async (label) => {
    const { selectedSession, sessions } = get()
    if (!selectedSession) return
    
    try {
      await api.patch(`/api/sessions/${selectedSession.session_id}/label`, { label })
      const updatedSession = { ...selectedSession, action_label: label }
      const updatedSessions = sessions.map(s => 
        s.session_id === selectedSession.session_id ? updatedSession : s
      )
      
      set({
        selectedSession: updatedSession,
        sessions: updatedSessions
      })
    } catch (err) {
      set({ error: 'Failed to save updated label to database' })
    }
  }
}))
