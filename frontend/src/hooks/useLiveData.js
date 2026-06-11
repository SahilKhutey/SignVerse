import { useEffect } from 'react'
import { useLiveStore } from '../store/live'

export function useLiveData() {
  const { latestFrame, status, connect, disconnect } = useLiveStore()

  useEffect(() => {
    connect()
    return () => disconnect()
  }, [connect, disconnect])

  return { latestFrame, status }
}
