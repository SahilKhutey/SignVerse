import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import api from '../api/client'
import { useSessionsStore } from '../store/sessions'
import Skeleton3DViewer from '../components/Skeleton3DViewer'
import PlaybackControls from '../components/viewer/PlaybackControls'
import ViewerPanel from '../components/viewer/ViewerPanel'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { EmptyState } from '../components/shared/EmptyState'

export default function ViewerPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const sessionId = searchParams.get('session')
  const { sessions, fetchSessions } = useSessionsStore()

  const [frames, setFrames] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  
  // Playback state
  const [currentFrame, setCurrentFrame] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [fps, setFps] = useState(30)

  useEffect(() => {
    fetchSessions()
  }, [])

  useEffect(() => {
    if (!sessionId) {
      setFrames([])
      return
    }

    setLoading(true)
    setError(null)
    setCurrentFrame(0)
    setPlaying(false)

    api.get(`/api/sessions/${sessionId}/frames?limit=5000`)
      .then(({ data }) => {
        if (data && data.length > 0) {
          setFrames(data)
        } else {
          setError('This session contains no skeleton frames.')
        }
      })
      .catch(err => {
        setError(err.message || 'Failed to retrieve motion frames.')
      })
      .finally(() => {
        setLoading(false)
      })
  }, [sessionId])

  // Playback loop
  useEffect(() => {
    if (!playing || frames.length === 0) return

    const intervalMs = 1000 / fps
    const timer = setInterval(() => {
      setCurrentFrame(prev => {
        if (prev >= frames.length - 1) {
          return 0 // loop
        }
        return prev + 1
      })
    }, intervalMs)

    return () => clearInterval(timer)
  }, [playing, frames, fps])

  const handleSelectSession = (id) => {
    setSearchParams({ session: id })
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '80vh' }}>
        <LoadingSpinner size={40} message="Retrieving 3D motion skeletal frames..." />
      </div>
    )
  }

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '1fr 340px',
      gap: 20,
      height: 'calc(100vh - 120px)',
      overflow: 'hidden',
    }}>
      {/* Left Column: 3D Canvas + Playback */}
      <div style={{
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
      }}>
        {/* Header toolbar */}
        <div style={{
          padding: '10px 16px',
          background: 'var(--bg-tertiary)',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 13, fontWeight: 600 }}>🌐 3D Motion Canvas</span>
            <select
              className="input"
              value={sessionId || ''}
              onChange={(e) => handleSelectSession(e.target.value)}
              style={{ marginTop: 0, padding: '4px 8px', width: 220, fontSize: 12 }}
            >
              <option value="">-- Choose Session --</option>
              {sessions.map(s => (
                <option key={s.session_id} value={s.session_id}>
                  {s.session_id} ({s.action_label || 'unlabeled'})
                </option>
              ))}
            </select>
          </div>
          {frames.length > 0 && (
            <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
              Frame {currentFrame + 1} / {frames.length}
            </div>
          )}
        </div>

        {/* Viewport */}
        <div style={{ flex: 1, position: 'relative', background: '#000' }}>
          {error ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--danger)', fontSize: 13 }}>
              ❌ {error}
            </div>
          ) : frames.length > 0 ? (
            <div style={{ position: 'absolute', inset: 0 }}>
              <Skeleton3DViewer
                frames={frames}
                currentFrame={currentFrame}
                playing={playing}
                onFrameChange={setCurrentFrame}
              />
            </div>
          ) : (
            <EmptyState
              icon="🌐"
              title="Select a Session"
              description="Choose a captured motion session from the dropdown to load the 3D skeleton playback player."
            />
          )}
        </div>

        {/* Playback Controls */}
        {frames.length > 0 && (
          <PlaybackControls
            current={currentFrame}
            total={frames.length}
            playing={playing}
            onPlayToggle={() => setPlaying(!playing)}
            onScrub={setCurrentFrame}
            fps={fps}
            onFpsChange={setFps}
          />
        )}
      </div>

      {/* Right Column: Keyframe stats / HOI detail */}
      <div style={{ overflowY: 'auto' }}>
        <ViewerPanel 
          frame={frames[currentFrame]} 
          sessionId={sessionId}
        />
      </div>
    </div>
  )
}
export { ViewerPage }
