import { useMotionStore } from '../store/motionStore'
import Skeleton3DViewer from './Skeleton3DViewer'
import TimelineScrubber from './TimelineScrubber'
import ActionLabeler from './ActionLabeler'
import ActionSegments from './ActionSegments'
import { SkeletonLoader, EmptyState } from './LoadingStates'
import MetricOverlay from './MetricOverlay'

export default function PoseOverlay() {
  const selectedSession = useMotionStore((state) => state.selectedSession)
  const frames = useMotionStore((state) => state.frames)
  const currentFrame = useMotionStore((state) => state.currentFrame)
  const playing = useMotionStore((state) => state.playing)
  const loading = useMotionStore((state) => state.loading)
  const setFrame = useMotionStore((state) => state.setFrame)
  const togglePlay = useMotionStore((state) => state.togglePlay)
  const updateLabel = useMotionStore((state) => state.updateLabel)

  if (loading) {
    return <SkeletonLoader height={500} />
  }

  if (!selectedSession) {
    return <EmptyState icon="🎬" title="No Session Selected" description="Upload a video or select a session from the Dataset Manager to view its 3D skeleton." />
  }

  return (
    <div style={{ width: '100%' }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '0.5rem',
        padding: '8px 12px',
        background: 'var(--bg-tertiary)',
        borderRadius: '8px',
        border: '1px solid var(--border)',
      }}>
        <div>
          <strong style={{ color: 'var(--accent)' }}>🎯 {selectedSession.session_id}</strong>
          <span style={{ marginLeft: '12px', color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
            {frames.length} frames · {selectedSession.action_label} · {selectedSession.source}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Frame: <strong style={{ color: 'var(--accent)' }}>{currentFrame}</strong>
          </span>
        </div>
      </div>

      <div style={{ position: 'relative', width: '100%' }}>
        <Skeleton3DViewer
          frames={frames}
          currentFrame={currentFrame}
          playing={playing}
          onFrameChange={setFrame}
        />
        {frames[currentFrame]?.metric_frame && (
          <MetricOverlay metricFrame={frames[currentFrame].metric_frame} />
        )}
      </div>

      <TimelineScrubber
        frame={currentFrame}
        total={frames.length}
        onChange={setFrame}
        playing={playing}
        onTogglePlay={togglePlay}
      />

      <ActionSegments
        sessionId={selectedSession.session_id}
        onSegmentClick={setFrame}
        totalFrames={frames.length}
      />

      <ActionLabeler
        sessionId={selectedSession.session_id}
        currentLabel={selectedSession.action_label}
        onUpdate={updateLabel}
      />
    </div>
  )
}
