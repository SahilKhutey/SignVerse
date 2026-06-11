import { useState } from 'react'
import api from '../../api/client'
import { useUiStore } from '../../store/ui'
import { useSessionsStore } from '../../store/sessions'
import Button from '../shared/Button'

export default function YouTubeCapture() {
  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const addToast = useUiStore(s => s.addToast)
  const addSession = useSessionsStore(s => s.addSession)

  const handleIngest = async () => {
    if (!url) return
    setLoading(true)
    addToast('Downloading and processing YouTube video...', 'info')
    try {
      const { data } = await api.post('/api/capture/youtube', 
        new URLSearchParams({ url }),
        { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
      )
      addToast('YouTube download & ingestion completed successfully!', 'success')
      if (data) {
        addSession(data)
      }
    } catch (e) {
      const msg = e.response?.data?.detail || e.response?.data?.error || e.message
      addToast(`YouTube capture failed: ${msg}`, 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <label className="label">YouTube Stream URL</label>
      <input
        type="text"
        className="input"
        placeholder="https://youtube.com/watch?v=..."
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        style={{ marginTop: 0 }}
      />
      <Button
        onClick={handleIngest}
        disabled={!url || loading}
        style={{ width: '100%' }}
      >
        {loading ? '⏳ Downloading YouTube stream...' : '📥 Ingest YouTube Link'}
      </Button>
    </div>
  )
}
export { YouTubeCapture }
