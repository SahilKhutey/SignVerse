import { useState, useRef } from 'react'

export default function LiveStream({ onComplete, onError }) {
  const [streaming, setStreaming] = useState(false)
  const [duration, setDuration] = useState(30)
  const wsRef = useRef(null)

  const start = () => {
    setStreaming(true)
    
    // Resolve relative WebSocket protocol and address
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${proto}//${window.location.host}/api/stream/camera`
    
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      ws.send(JSON.stringify({ duration }))
    }

    ws.onmessage = (evt) => {
      const msg = JSON.parse(evt.data)
      if (msg.type === 'complete') {
        onComplete?.({
          session_id: msg.payload.session_id,
          frames_extracted: msg.payload.frame_count,
          metadata: { 
            status: 'ready',
            duration_sec: duration,
            fps: 30.0
          },
        })
        stop()
      } else if (msg.type === 'error') {
        onError?.(msg.payload.msg)
        stop()
      }
    }

    ws.onclose = () => setStreaming(false)
    ws.onerror = () => {
      onError?.('WebSocket connection error. Verify that the API server is active.')
      setStreaming(false)
    }
  }

  const stop = () => {
    wsRef.current?.close()
    setStreaming(false)
  }

  return (
    <div>
      <label style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', display: 'block', marginBottom: '0.5rem' }}>
        Recording Limit: <strong>{duration}s</strong>
      </label>
      <input
        type="range"
        min="5"
        max="120"
        value={duration}
        onChange={(e) => setDuration(Number(e.target.value))}
        style={{ width: '100%' }}
      />
      <button
        className="btn"
        onClick={streaming ? stop : start}
        style={{ background: streaming ? 'var(--danger)' : 'var(--accent)', color: 'white' }}
      >
        {streaming ? '⏹ Stop Recording' : '🎥 Open Webcam stream'}
      </button>
    </div>
  )
}
