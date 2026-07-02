import { useState } from 'react'
import WebcamCapture from '../components/capture/WebcamCapture'
import VideoUpload from '../components/capture/VideoUpload'
import YouTubeCapture from '../components/capture/YouTubeCapture'
import CapturePanel from '../components/capture/CapturePanel'
import IngestionQueue from '../components/capture/IngestionQueue'

export default function CapturePage() {
  const [activeTab, setActiveTab] = useState('upload')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 800, margin: '0 auto' }}>
      <div className="card">
        <h3 className="card-title">🎥 Ingestion Sources</h3>
        <div style={{
          display: 'flex',
          borderBottom: '1px solid var(--border)',
          marginBottom: 20,
        }}>
          <TabButton active={activeTab === 'upload'} onClick={() => setActiveTab('upload')} label="📤 Upload Video" />
          <TabButton active={activeTab === 'webcam'} onClick={() => setActiveTab('webcam')} label="🎥 Live Webcam" />
          <TabButton active={activeTab === 'youtube'} onClick={() => setActiveTab('youtube')} label="📺 YouTube Link" />
        </div>

        {activeTab === 'upload' && <VideoUpload />}
        {activeTab === 'webcam' && <WebcamCapture />}
        {activeTab === 'youtube' && <YouTubeCapture />}
      </div>
      
      <IngestionQueue />
      <CapturePanel />
    </div>
  )
}

function TabButton({ active, onClick, label }) {
  return (
    <button
      onClick={onClick}
      style={{
        background: 'transparent',
        border: 'none',
        borderBottom: `2px solid ${active ? 'var(--accent)' : 'transparent'}`,
        color: active ? 'var(--accent)' : 'var(--text-secondary)',
        padding: '10px 20px',
        fontSize: 13,
        fontWeight: 600,
        cursor: 'pointer',
        transition: 'all 0.2s',
      }}
    >
      {label}
    </button>
  )
}
export { CapturePage }
