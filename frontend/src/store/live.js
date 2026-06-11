import { create } from 'zustand'
import { WebSocketManager } from '../api/websocket'

export const useLiveStore = create((set, get) => ({
  latestFrame: null,
  status: 'disconnected',
  serverFps: 0,
  subscriberCount: 0,
  wsManager: null,
  videoWs: null,
  liveStats: {
    framesProcessed: 0,
    avgLatency: 0,
    startedAt: null,
  },

  connect() {
    if (get().wsManager) return
    
    const ws = new WebSocketManager('/ws/live')
    ws.onMessage((data) => {
      if (data.type === 'frame') {
        set((state) => ({
          latestFrame: data.data,
          serverFps: data.meta?.server_fps || 0,
          subscriberCount: data.meta?.subscriber_count || 0,
          liveStats: {
            framesProcessed: state.liveStats.framesProcessed + 1,
            avgLatency: data.data?.processing_time_ms || 0,
            startedAt: state.liveStats.startedAt || Date.now(),
          },
        }))
      }
    })
    ws.onStatusChange((status) => set({ status }))
    ws.connect()
    
    // Also connect to video feed
    const videoWs = new WebSocketManager('/ws/live/video', { binaryType: 'arraybuffer' })
    videoWs.onMessage((data) => {
      // Binary JPEG data - handled by LiveVideoFeed component
    })
    videoWs.connect()
    
    set({ wsManager: ws, videoWs })
  },

  disconnect() {
    get().wsManager?.disconnect()
    get().videoWs?.disconnect()
    set({
      wsManager: null,
      videoWs: null,
      status: 'disconnected',
      latestFrame: null,
      liveStats: { framesProcessed: 0, avgLatency: 0, startedAt: null },
    })
  },

  reset() {
    set({
      latestFrame: null,
      liveStats: { framesProcessed: 0, avgLatency: 0, startedAt: null },
    })
  },
}))
