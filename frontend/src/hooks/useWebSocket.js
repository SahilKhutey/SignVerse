import { useEffect, useState, useRef } from 'react'
import { WebSocketManager } from '../api/websocket'

export function useWebSocket(path, onMessage) {
  const [status, setStatus] = useState('disconnected')
  const wsRef = useRef(null)
  const messageCallbackRef = useRef(onMessage)

  useEffect(() => {
    messageCallbackRef.current = onMessage
  }, [onMessage])

  useEffect(() => {
    const ws = new WebSocketManager(path)
    wsRef.current = ws

    const unsubStatus = ws.onStatusChange(setStatus)
    const unsubMsg = ws.onMessage((data) => {
      if (messageCallbackRef.current) {
        messageCallbackRef.current(data)
      }
    })

    ws.connect()

    return () => {
      unsubStatus()
      unsubMsg()
      ws.disconnect()
    }
  }, [path])

  const send = (data) => {
    if (wsRef.current) {
      wsRef.current.send(data)
    }
  }

  return { status, send }
}
