import { useState } from 'react'
import axios from 'axios'

export default function UploadPanel({ onSuccess, onError }) {
  const [file, setFile] = useState(null)
  const [ytUrl, setYtUrl] = useState('')
  const [tab, setTab] = useState('file') // 'file' | 'youtube'
  const [loading, setLoading] = useState(false)

  const handleFileUpload = async () => {
    if (!file) return onError?.('No local file selected')
    setLoading(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const { data } = await axios.post('/api/capture/upload', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      onSuccess?.(data)
    } catch (e) {
      onError?.(e.response?.data?.detail || e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleYouTube = async () => {
    if (!ytUrl) return onError?.('No YouTube link specified')
    setLoading(true)
    try {
      const { data } = await axios.post('/api/capture/youtube', 
        new URLSearchParams({ url: ytUrl }),
        { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
      )
      onSuccess?.(data)
    } catch (e) {
      onError?.(e.response?.data?.detail || e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
        <button 
          className={`btn ${tab === 'file' ? '' : 'btn-secondary'}`} 
          onClick={() => setTab('file')}
          style={{ flex: 1 }}
        >
          Local File
        </button>
        <button 
          className={`btn ${tab === 'youtube' ? '' : 'btn-secondary'}`} 
          onClick={() => setTab('youtube')}
          style={{ flex: 1 }}
        >
          YouTube Link
        </button>
      </div>

      {tab === 'file' ? (
        <>
          <input
            type="file"
            accept="video/*"
            className="input"
            onChange={(e) => setFile(e.target.files?.[0])}
          />
          <button 
            className="btn" 
            onClick={handleFileUpload} 
            disabled={!file || loading}
          >
            {loading ? '⏳ Processing video frames...' : '🚀 Process Video'}
          </button>
        </>
      ) : (
        <>
          <input
            type="text"
            placeholder="https://youtube.com/watch?v=..."
            className="input"
            value={ytUrl}
            onChange={(e) => setYtUrl(e.target.value)}
          />
          <button 
            className="btn" 
            onClick={handleYouTube} 
            disabled={!ytUrl || loading}
          >
            {loading ? '⏳ Downloading YouTube stream...' : '📥 Download & Ingest'}
          </button>
        </>
      )}
    </div>
  )
}
