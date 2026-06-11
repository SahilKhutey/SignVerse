import { useEffect, useState } from 'react'
import { useLiveStore } from '../store/live'
import LiveVideoFeed from '../components/live/LiveVideoFeed'
import LiveSkeletonOverlay from '../components/live/LiveSkeletonOverlay'
import Live3DSkeleton from '../components/live/Live3DSkeleton'
import LiveStatsPanel from '../components/live/LiveStatsPanel'
import LiveInteractionLog from '../components/live/LiveInteractionLog'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'

export default function LivePage() {
  const { connect, disconnect, status, latestFrame, serverFps, subscriberCount, liveStats } = useLiveStore()
  const [showVideo, setShowVideo] = useState(true)
  const [show3D, setShow3D] = useState(true)
  const [showFace, setShowFace] = useState(true)
  const [showHands, setShowHands] = useState(true)
  const [showObjects, setShowObjects] = useState(true)
  const [autoConnect] = useState(true)
  
  useEffect(() => {
    if (autoConnect) {
      connect()
      return () => disconnect()
    }
  }, [autoConnect, connect, disconnect])
  
  const wsStatusColor = {
    connected: '#10b981',
    connecting: '#f59e0b',
    disconnected: '#6b7280',
    error: '#ef4444',
  }[status]
  
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '1fr 1fr 340px',
      gap: 16,
      padding: 16,
      height: 'calc(100vh - 120px)',
      overflow: 'hidden',
    }}>
      {/* LEFT: Video + Skeleton Overlay */}
      <Panel 
        title="📷 2D Live View" 
        status={status}
        statusColor={wsStatusColor}
        controls={
          <>
            <ToggleBtn active={showVideo} onClick={() => setShowVideo(!showVideo)} label="Video" />
            <ToggleBtn active={!showVideo} onClick={() => setShowVideo(false)} label="Skeleton" />
          </>
        }
      >
        <div style={{ position: 'relative', flex: 1, background: '#000' }}>
          {showVideo && (
            <div style={{ position: 'absolute', inset: 0 }}>
              <LiveVideoFeed />
            </div>
          )}
          <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
            {status === 'connected' ? (
              <LiveSkeletonOverlay
                frame={latestFrame}
                width={640}
                height={480}
                showFace={showFace}
                showHands={showHands}
                showObjects={showObjects}
              />
            ) : (
              <div style={{ 
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                width: '100%', height: '100%', color: '#9ca3c4',
              }}>
                {status === 'connecting' ? <LoadingSpinner message="Connecting..." /> : 'Disconnected'}
              </div>
            )}
          </div>
        </div>
        
        {/* Layer toggles */}
        <div style={{
          padding: 8,
          background: 'var(--bg-tertiary)',
          display: 'flex',
          gap: 6,
          justifyContent: 'center',
          borderTop: '1px solid var(--border)',
        }}>
          <ToggleBtn small active={showFace} onClick={() => setShowFace(!showFace)} label="👤 Face" />
          <ToggleBtn small active={showHands} onClick={() => setShowHands(!showHands)} label="✋ Hands" />
          <ToggleBtn small active={showObjects} onClick={() => setShowObjects(!showObjects)} label="📦 Objects" />
        </div>
      </Panel>
      
      {/* CENTER: 3D Skeleton */}
      <Panel 
        title="🌐 3D Skeleton (Live)" 
        status={status}
        statusColor={wsStatusColor}
      >
        <div style={{ flex: 1, position: 'relative' }}>
          {show3D ? (
            <Live3DSkeleton frame={latestFrame} />
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#9ca3c4' }}>
              3D disabled
            </div>
          )}
        </div>
      </Panel>
      
      {/* RIGHT: Stats + Interaction Log */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, overflow: 'hidden' }}>
        <LiveStatsPanel 
          frame={latestFrame}
          serverFps={serverFps}
          subscriberCount={subscriberCount}
          liveStats={liveStats}
        />
        <div style={{ flex: 1, overflow: 'hidden' }}>
          <LiveInteractionLog frame={latestFrame} />
        </div>
      </div>
    </div>
  )
}

function Panel({ title, status, statusColor, controls, children }) {
  return (
    <div style={{
      background: 'var(--bg-secondary)',
      borderRadius: 10,
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
      border: '1px solid var(--border)',
    }}>
      <div style={{
        background: 'var(--bg-tertiary)',
        padding: '10px 14px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottom: '1px solid var(--border)',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{title}</span>
          {status && (
            <span style={{
              width: 8, height: 8, borderRadius: '50%',
              background: statusColor,
              boxShadow: `0 0 8px ${statusColor}`,
            }} />
          )}
        </div>
        <div style={{ display: 'flex', gap: 4 }}>{controls}</div>
      </div>
      {children}
    </div>
  )
}

function ToggleBtn({ active, onClick, label, small }) {
  return (
    <button
      onClick={onClick}
      style={{
        background: active ? 'var(--accent)' : 'transparent',
        color: active ? 'var(--bg-primary)' : 'var(--text-secondary)',
        border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
        borderRadius: 4,
        padding: small ? '2px 8px' : '4px 10px',
        fontSize: small ? 10 : 11,
        fontWeight: 600,
        cursor: 'pointer',
      }}
    >
      {label}
    </button>
  )
}
