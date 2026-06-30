import { create } from 'zustand'

export const useUiStore = create((set) => ({
  theme: localStorage.getItem('theme') || 'dark',
  sidebarExpanded: true,
  toasts: [],

  toggleTheme() {
    set((state) => {
      const nextTheme = state.theme === 'dark' ? 'light' : 'dark'
      localStorage.setItem('theme', nextTheme)
      return { theme: nextTheme }
    })
  },

  toggleSidebar() {
    set((state) => ({ sidebarExpanded: !state.sidebarExpanded }))
  },

  addToast(message, type = 'success') {
    const id = (typeof crypto !== 'undefined' && crypto.randomUUID)
      ? crypto.randomUUID()
      : Math.random().toString(36).substring(2, 15);
    set((state) => ({
      toasts: [...state.toasts, { id, message, type }]
    }))
    setTimeout(() => {
      get().removeToast(id)
    }, 4000)
  },

  removeToast(id) {
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id)
    }))
  }
}))

// Support for timeout within the Zustand callback
const get = () => useUiStore.getState()
