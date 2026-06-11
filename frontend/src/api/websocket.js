/**
 * Reusable WebSocket manager with auto-reconnect.
 */
import { WS_URL } from './client'

export class WebSocketManager {
  constructor(path, options = {}) {
    this.path = path
    this.url = `${WS_URL}${path}`
    this.ws = null
    this.handlers = new Set()
    this.statusHandlers = new Set()
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = options.maxReconnectAttempts || 10
    this.reconnectDelay = 1000
    this.shouldReconnect = true
    this.status = 'disconnected'
    this.binaryType = options.binaryType || 'blob'
  }

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) return
    
    this.setStatus('connecting')
    this.ws = new WebSocket(this.url)
    if (this.binaryType) {
      this.ws.binaryType = this.binaryType
    }
    
    this.ws.onopen = () => {
      this.reconnectAttempts = 0
      this.setStatus('connected')
    }
    
    this.ws.onmessage = (event) => {
      // Direct pass for binary data
      if (this.binaryType === 'arraybuffer' || event.data instanceof ArrayBuffer || event.data instanceof Blob) {
        this.handlers.forEach(h => h(event))
        return
      }
      try {
        const data = JSON.parse(event.data)
        this.handlers.forEach(h => h(data))
      } catch (e) {
        console.error('[WS] Parse error:', e)
      }
    }
    
    this.ws.onclose = () => {
      this.setStatus('disconnected')
      if (this.shouldReconnect && this.reconnectAttempts < this.maxReconnectAttempts) {
        const delay = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts), 30000)
        this.reconnectAttempts++
        setTimeout(() => this.connect(), delay)
      }
    }
    
    this.ws.onerror = (e) => {
      console.error('[WS] Error:', e)
      this.setStatus('error')
    }
  }

  disconnect() {
    this.shouldReconnect = false
    if (this.ws) this.ws.close()
  }

  send(data) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(typeof data === 'string' ? data : JSON.stringify(data))
    }
  }

  onMessage(handler) {
    this.handlers.add(handler)
    return () => this.handlers.delete(handler)
  }

  onStatusChange(handler) {
    this.statusHandlers.add(handler)
    handler(this.status)
    return () => this.statusHandlers.delete(handler)
  }

  setStatus(status) {
    this.status = status
    this.statusHandlers.forEach(h => h(status))
  }
}
