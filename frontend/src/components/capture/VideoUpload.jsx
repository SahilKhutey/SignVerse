import { useState } from 'react'
import api from '../../api/client'
import { useUiStore } from '../../store/ui'
import { useSessionsStore } from '../../store/sessions'
import Button from '../shared/Button'

export default function VideoUpload() {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const addToast = useUiStore(s => s.addToast)
  const addSession = useSessionsStore(s => s.addSession)

  const handleUpload = async () => {
    if (!file) return
    setLoading(true)
    addToast('Uploading video and extracting 3D motion path...', 'info')
    try {
      const fd = new FormData()
      fd.append('file', file)
      const { data } = await api.post('/api/capture/upload', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      addToast('Motion extraction completed successfully!', 'success')
      if (data) {
        addSession(data)
      }
    } catch (e) {
      const msg = e.response?.data?.detail || e.response?.data?.error || e.message
      addToast(`Upload failed: ${msg}`, 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <label className="label">Select Local Video File</label>
      <input
        type="file"
        accept="video/*"
        className="input"
        onChange={(e) => setFile(e.target.files?.[0])}
        style={{ marginTop: 0 }}
      />
      <Button
        onClick={handleUpload}
        disabled={!file || loading}
        style={{ width: '100%' }}
      >
        {loading ? '⏳ Processing video frames...' : '🚀 Process & Ingest Video'}
      </Button>
    </div>
  )
}
export { VideoUpload }
