import { Badge } from '../shared/Badge'
import { formatDate } from '../../utils/formatters'
import { SOURCE_TYPES } from '../../utils/constants'

export default function SessionCard({ session, isSelected, onSelect, onDelete }) {
  const meta = SOURCE_TYPES[session.source_type] || { label: 'Unknown', icon: '❓' }

  return (
    <div 
      onClick={() => onSelect(session.session_id)}
      style={{
        background: isSelected ? 'var(--bg-tertiary)' : 'var(--bg-secondary)',
        border: `1px solid ${isSelected ? 'var(--accent)' : 'var(--border)'}`,
        borderRadius: 10,
        padding: 12,
        cursor: 'pointer',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        transition: 'all 0.2s',
      }}
      className="session-card"
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 14 }}>{meta.icon}</span>
          <span style={{ fontSize: 11, fontWeight: 700, fontFamily: 'monospace', color: isSelected ? 'var(--accent)' : 'var(--text-primary)' }}>
            {session.session_id}
          </span>
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation()
            onDelete(session.session_id)
          }}
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--text-secondary)',
            cursor: 'pointer',
            fontSize: 12,
            padding: 4,
          }}
          title="Delete session"
        >
          🗑️
        </button>
      </div>

      <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
        Name: <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{session.name || 'Unnamed'}</span>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 10, color: 'var(--text-secondary)' }}>
        <span>Frames: <strong>{session.frame_count}</strong></span>
        <span>FPS: <strong>{session.fps?.toFixed(0) || 30}</strong></span>
        <span>Height: <strong>{session.person_height_m ? `${session.person_height_m.toFixed(2)}m` : '—'}</strong></span>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 4 }}>
        <Badge status={session.action_label ? 'neutral' : 'processing'}>
          {session.action_label || 'unlabeled'}
        </Badge>
        <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
          {formatDate(session.created_at)}
        </span>
      </div>
    </div>
  )
}
export { SessionCard }
