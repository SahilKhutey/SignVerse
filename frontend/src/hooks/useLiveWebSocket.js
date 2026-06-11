import { useEffect, useRef, useState, useCallback } from 'react'

const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'

/**
 * Connects to the live perception WebSocket.
 * Returns the latest frame data + connection status.
 */
export function useLiveWebSocket(autoConnect = true) {
  const [latestFrame, setLatestFrame] = useState(null)
  const [status, setStatus] = useState('disconnected')  // disconnected | connecting | connected | error
  const [serverFps, setServerFps] = useState(0)
  const [subscriberCount, setSubscriberCount] = useState(0)
  const wsRef = useRef(null)
  const reconnectTimerRef = useRef(null)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    setStatus('connecting')
    
    // Resolve full WS URL (supporting relative paths for production/proxies)
    let wsUrl = `${WS_BASE}/ws/live`
    if (WS_BASE.startsWith('/')) {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      wsUrl = `${protocol}//${window.location.host}${WS_BASE}/ws/live`
    }
    
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      console.log('[LiveWS] Connected')
      setStatus('connected')
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'frame') {
          setLatestFrame(msg.data)
          if (msg.meta) {
            setServerFps(msg.meta.server_fps)
            setSubscriberCount(msg.meta.subscriber_count)
          }
        } else if (msg.type === 'ready') {
          console.log('[LiveWS]', msg.message)
        } else if (msg.type === 'ping') {
          ws.send(JSON.stringify({ action: 'pong' }))
        }
      } catch (e) {
        console.error('[LiveWS] Parse error:', e)
      }
    }

    ws.onerror = (e) => {
      console.error('[LiveWS] Error:', e)
      setStatus('error')
    }

    ws.onclose = () => {
      console.log('[LiveWS] Disconnected')
      setStatus('disconnected')
      // Auto-reconnect after 2s
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = setTimeout(() => {
        if (autoConnect) connect()
      }, 2000)
    }
  }, [autoConnect])

  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setStatus('disconnected')
  }, [])

  const sendControl = useCallback((action) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action }))
    }
  }, [])

  useEffect(() => {
    if (autoConnect) connect()
    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      wsRef.current?.close()
    }
  }, [autoConnect, connect])

  return {
    latestFrame,
    status,
    serverFps,
    subscriberCount,
    connect,
    disconnect,
    sendControl,
  }
}
