import { useNavigate } from 'react-router-dom'
import { LoadingSpinner } from '../shared/LoadingSpinner'
import LabelEditor from './LabelEditor'
import ActionSegments from './ActionSegments'
import Button from '../shared/Button'
import { SOURCE_TYPES } from '../../utils/constants'
import { formatDate } from '../../utils/formatters'

export default function SessionDetail({ session, loading }) {
  const navigate = useNavigate()

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', minHeight: 200 }}>
        <LoadingSpinner message="Loading session detail..." />
      </div>
    )
  }

  if (!session) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: 200, color: 'var(--text-secondary)', fontSize: 13 }}>
        Select a session from the list to view details
      </div>
    )
  }

  const meta = SOURCE_TYPES[session.source_type] || { label: 'Unknown', icon: '❓' }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Session Title */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 18 }}>{meta.icon}</span>
          <h4 style={{ fontSize: 13, fontWeight: 700, margin: 0, color: 'var(--accent)', fontFamily: 'monospace' }}>
            {session.session_id}
          </h4>
        </div>
        <p style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 4 }}>
          Created: {formatDate(session.created_at)}
        </p>
      </div>

      {/* Basic Metrics */}
      <div className="card" style={{ padding: 12 }}>
        <h5 style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8, letterSpacing: 1 }}>📊 METRICS</h5>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <DetailRow label="Name" value={session.name || 'Unnamed'} />
          <DetailRow label="Source" value={meta.label} />
          <DetailRow label="Frames" value={session.frame_count} />
          <DetailRow label="FPS" value={session.fps?.toFixed(1) || 30.0} />
          <DetailRow label="Height" value={session.person_height_m ? `${session.person_height_m.toFixed(2)} m` : '—'} />
          <DetailRow label="Scale Factor" value={session.scale_factor_mean ? session.scale_factor_mean.toFixed(2) : '—'} />
        </div>
      </div>

      {/* Label Editor */}
      <LabelEditor sessionId={session.session_id} initialLabel={session.action_label} />

      {/* Action Segments / Timeline */}
      <ActionSegments sessionId={session.session_id} segments={session.segments || []} />

      {/* Action Buttons */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
        <Button onClick={() => navigate(`/viewer?session=${session.session_id}`)} style={{ width: '100%' }}>
          🌐 View in 3D Motion Canvas
        </Button>
        <Button variant="secondary" onClick={() => navigate(`/export?session=${session.session_id}`)} style={{ width: '100%' }}>
          📦 Go to Export Center
        </Button>
      </div>
    </div>
  )
}

function DetailRow({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
      <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
      <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{value}</span>
    </div>
  )
}
export { SessionDetail }
