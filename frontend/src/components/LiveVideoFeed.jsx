import { useEffect, useRef, useState } from 'react'

const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'

/**
 * Live raw video feed from webcam.
 * Connects to /ws/live/video WebSocket and displays JPEG frames.
 */
export default function LiveVideoFeed({ onConnectionChange }) {
  const imgRef = useRef(null)
  const wsRef = useRef(null)
  const [connected, setConnected] = useState(false)
  const [fps, setFps] = useState(0)
  const fpsCounter = useRef({ frames: 0, lastTime: Date.now() })

  useEffect(() => {
    // Resolve relative WebSocket URL for production / proxies
    let wsUrl = `${WS_BASE}/ws/live/video`
    if (WS_BASE.startsWith('/')) {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      wsUrl = `${protocol}//${window.location.host}${WS_BASE}/ws/live/video`
    }

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws
    ws.binaryType = 'arraybuffer'

    ws.onopen = () => {
      setConnected(true)
      onConnectionChange?.(true)
    }

    ws.onclose = () => {
      setConnected(false)
      onConnectionChange?.(false)
    }

    ws.onerror = () => {
      setConnected(false)
      onConnectionChange?.(false)
    }

    ws.onmessage = (event) => {
      // Binary JPEG data
      const blob = new Blob([event.data], { type: 'image/jpeg' })
      const url = URL.createObjectURL(blob)

      if (imgRef.current) {
        const oldUrl = imgRef.current.src
        imgRef.current.src = url
        // Revoke after a tick
        if (oldUrl && oldUrl.startsWith('blob:')) {
          setTimeout(() => URL.revokeObjectURL(oldUrl), 100)
        }
      }

      // FPS tracking
      fpsCounter.current.frames++
      const now = Date.now()
      if (now - fpsCounter.current.lastTime >= 1000) {
        setFps(fpsCounter.current.frames)
        fpsCounter.current.frames = 0
        fpsCounter.current.lastTime = now
      }
    }

    return () => {
      ws.close()
    }
  }, [onConnectionChange])

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <img
        ref={imgRef}
        alt="Live feed"
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'contain',
          background: '#000',
        }}
      />
      {/* Live indicator */}
      <div
        style={{
          position: 'absolute',
          top: 10,
          right: 10,
          background: connected ? 'rgba(239, 68, 68, 0.9)' : 'rgba(107, 114, 128, 0.9)',
          color: 'white',
          padding: '4px 10px',
          borderRadius: 4,
          fontSize: 12,
          fontWeight: 600,
          display: 'flex',
          alignItems: 'center',
          gap: 6,
        }}
      >
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: 'white',
            animation: connected ? 'pulse 1.5s infinite' : 'none',
          }}
        />
        {connected ? `LIVE · ${fps} FPS` : 'OFFLINE'}
      </div>
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
      `}</style>
    </div>
  )
}
