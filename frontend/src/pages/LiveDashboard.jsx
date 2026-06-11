import { useState } from 'react'
import { useLiveWebSocket } from '../hooks/useLiveWebSocket'
import LiveVideoFeed from '../components/LiveVideoFeed'
import LiveSkeletonOverlay from '../components/LiveSkeletonOverlay'
import Live3DSkeleton from '../components/Live3DSkeleton'
import LiveStatsPanel from '../components/LiveStatsPanel'

export default function LiveDashboard() {
  const { latestFrame, status, serverFps, subscriberCount, connect, disconnect } = useLiveWebSocket(true)
  const [showVideo, setShowVideo] = useState(true)
  const [showOverlay, setShowOverlay] = useState(true)
  const [show3D, setShow3D] = useState(true)
  const [showFace, setShowFace] = useState(true)
  const [showHands, setShowHands] = useState(true)
  const [showObjects, setShowObjects] = useState(true)

  const wsStatusColor = {
    connected: '#10b981',
    connecting: '#f59e0b',
    disconnected: '#6b7280',
    error: '#ef4444',
  }[status]

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '1fr 1fr 320px',
      gap: 16,
      padding: 16,
      height: 'calc(100vh - 120px)',
      background: '#0a0e27',
      minHeight: '500px',
    }}>

      {/* === LEFT: 2D Video + Skeleton Overlay === */}
      <div style={{
        background: '#131836',
        borderRadius: 12,
        overflow: 'hidden',
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        border: '1px solid #2a3158',
      }}>
        <PanelHeader
          title="📷 2D Live View"
          status={status}
          statusColor={wsStatusColor}
          controls={
            <div style={{ display: 'flex', gap: 6 }}>
              <ToggleBtn active={showVideo} onClick={() => setShowVideo(!showVideo)} label="Video" />
              <ToggleBtn active={showOverlay} onClick={() => setShowOverlay(!showOverlay)} label="Skeleton" />
            </div>
          }
        />

        <div style={{ flex: 1, position: 'relative', background: '#000' }}>
          {/* Stack: video on bottom, overlay on top */}
          {showVideo && (
            <div style={{ position: 'absolute', inset: 0 }}>
              <LiveVideoFeed />
            </div>
          )}
          {showOverlay && (
            <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
              <LiveSkeletonOverlay
                frame={latestFrame}
                width={640}
                height={480}
                showFace={showFace}
                showHands={showHands}
                showObjects={showObjects}
              />
            </div>
          )}
        </div>

        {/* Layer toggles */}
        <div style={{
          background: '#0a0e27',
          padding: 8,
          display: 'flex',
          gap: 6,
          justifyContent: 'center',
          borderTop: '1px solid #2a3158',
        }}>
          <ToggleBtn small active={showFace} onClick={() => setShowFace(!showFace)} label="👤 Face" />
          <ToggleBtn small active={showHands} onClick={() => setShowHands(!showHands)} label="✋ Hands" />
          <ToggleBtn small active={showObjects} onClick={() => setShowObjects(!showObjects)} label="📦 Objects" />
        </div>
      </div>

      {/* === CENTER: 3D Skeleton Viewer === */}
      <div style={{
        background: '#131836',
        borderRadius: 12,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        border: '1px solid #2a3158',
      }}>
        <PanelHeader
          title="🌐 3D Skeleton (Live)"
          status={status}
          statusColor={wsStatusColor}
          controls={
            <ToggleBtn active={show3D} onClick={() => setShow3D(!show3D)} label="3D" />
          }
        />
        <div style={{ flex: 1, position: 'relative' }}>
          {show3D && <Live3DSkeleton frame={latestFrame} />}
        </div>
      </div>

      {/* === RIGHT: Stats Panel === */}
      <div style={{
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
      }}>
        <LiveStatsPanel
          frame={latestFrame}
          serverFps={serverFps}
          subscriberCount={subscriberCount}
        />
      </div>

    </div>
  )
}

function PanelHeader({ title, status, statusColor, controls }) {
  return (
    <div style={{
      background: '#1c2348',
      padding: '12px 16px',
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      borderBottom: '1px solid #2a3158',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <h3 style={{ margin: 0, fontSize: 14, color: '#e4e7f1', fontWeight: 600 }}>{title}</h3>
        <span style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: statusColor,
          display: 'inline-block',
          boxShadow: `0 0 8px ${statusColor}`,
        }} />
        <span style={{ fontSize: 10, color: '#9ca3c4', textTransform: 'capitalize' }}>{status}</span>
      </div>
      {controls}
    </div>
  )
}

function ToggleBtn({ active, onClick, label, small }) {
  return (
    <button
      onClick={onClick}
      style={{
        background: active ? '#7c3aed' : '#2a3158',
        border: 'none',
        borderRadius: 4,
        color: 'white',
        padding: small ? '2px 8px' : '4px 10px',
        fontSize: small ? 10 : 12,
        cursor: 'pointer',
        fontWeight: 500,
        transition: 'all 0.2s',
      }}
    >
      {label}
    </button>
  )
}
