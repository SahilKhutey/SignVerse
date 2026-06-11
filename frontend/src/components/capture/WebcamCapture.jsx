import { useState, useRef } from 'react'
import { useUiStore } from '../../store/ui'
import { useSessionsStore } from '../../store/sessions'
import Button from '../shared/Button'
import { WS_URL } from '../../api/client'

export default function WebcamCapture() {
  const [streaming, setStreaming] = useState(false)
  const [duration, setDuration] = useState(30)
  const wsRef = useRef(null)
  const addToast = useUiStore(s => s.addToast)
  const addSession = useSessionsStore(s => s.addSession)

  const start = () => {
    setStreaming(true)
    
    // Convert WS_URL base if needed
    const wsBase = WS_URL.replace(/^http/, 'ws')
    const wsUrl = `${wsBase}/api/stream/camera`
    
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      ws.send(JSON.stringify({ duration }))
      addToast('Webcam capture stream opened', 'info')
    }

    ws.onmessage = (evt) => {
      const msg = JSON.parse(evt.data)
      if (msg.type === 'complete') {
        addToast('Webcam motion capture completed!', 'success')
        if (msg.payload) {
          addSession(msg.payload)
        }
        stop()
      } else if (msg.type === 'error') {
        addToast(`Webcam capture failed: ${msg.payload.msg}`, 'error')
        stop()
      }
    }

    ws.onclose = () => setStreaming(false)
    ws.onerror = () => {
      addToast('Webcam WebSocket connection error.', 'error')
      setStreaming(false)
    }
  }

  const stop = () => {
    wsRef.current?.close()
    setStreaming(false)
  }

  return (
    <div>
      <label className="label" style={{ marginBottom: 8 }}>
        Recording Limit: <strong>{duration} seconds</strong>
      </label>
      <input
        type="range"
        min="5"
        max="120"
        value={duration}
        onChange={(e) => setDuration(Number(e.target.value))}
        style={{ width: '100%', accentColor: 'var(--accent)', marginBottom: 20 }}
      />
      <Button
        variant={streaming ? 'danger' : 'primary'}
        onClick={streaming ? stop : start}
        style={{ width: '100%' }}
      >
        {streaming ? '⏹ Stop Recording' : '🎥 Open Webcam Stream'}
      </Button>
    </div>
  )
}
export { WebcamCapture }
