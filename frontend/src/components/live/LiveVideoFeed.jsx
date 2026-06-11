import { useEffect, useRef, useState } from 'react'
import { useLiveStore } from '../../store/live'

export default function LiveVideoFeed() {
  const videoWs = useLiveStore(s => s.videoWs)
  const imgRef = useRef(null)
  const [fps, setFps] = useState(0)
  const fpsCounter = useRef({ frames: 0, lastTime: Date.now() })
  
  useEffect(() => {
    if (!videoWs) return
    
    const handler = (event) => {
      // Binary JPEG
      const blob = new Blob([event.data], { type: 'image/jpeg' })
      const url = URL.createObjectURL(blob)
      if (imgRef.current) {
        const oldUrl = imgRef.current.src
        imgRef.current.src = url
        if (oldUrl && oldUrl.startsWith('blob:')) {
          setTimeout(() => URL.revokeObjectURL(oldUrl), 100)
        }
      }
      fpsCounter.current.frames++
      const now = Date.now()
      if (now - fpsCounter.current.lastTime >= 1000) {
        setFps(fpsCounter.current.frames)
        fpsCounter.current.frames = 0
        fpsCounter.current.lastTime = now
      }
    }
    
    // Override onMessage to handle binary
    if (videoWs.ws) {
      videoWs.ws.addEventListener('message', handler)
    }
    return () => {
      if (videoWs.ws) {
        videoWs.ws.removeEventListener('message', handler)
      }
    }
  }, [videoWs])
  
  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <img ref={imgRef} alt="Live" style={{ width: '100%', height: '100%', objectFit: 'contain', background: '#000' }} />
      <div style={{
        position: 'absolute', top: 8, right: 8,
        background: 'rgba(239, 68, 68, 0.9)', color: 'white',
        padding: '3px 8px', borderRadius: 4, fontSize: 10, fontWeight: 600,
        display: 'flex', alignItems: 'center', gap: 5,
      }}>
        <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'white', animation: 'pulse 1.5s infinite' }} />
        LIVE · {fps} FPS
      </div>
      <style>{`@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }`}</style>
    </div>
  )
}
export { LiveVideoFeed }
