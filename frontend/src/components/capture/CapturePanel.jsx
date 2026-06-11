import { useSessionsStore } from '../../store/sessions'
import { useNavigate } from 'react-router-dom'
import { SOURCE_TYPES } from '../../utils/constants'
import { formatDate } from '../../utils/formatters'

export default function CapturePanel() {
  const sessions = useSessionsStore(s => s.sessions)
  const navigate = useNavigate()

  const recent = sessions.slice(0, 3)

  return (
    <div className="card">
      <h3 className="card-title">📂 Recent Ingestions</h3>
      {recent.length === 0 ? (
        <p style={{ fontSize: 12, color: 'var(--text-secondary)', padding: '10px 0' }}>
          No videos processed yet. Choose an ingestion source above to begin.
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 12 }}>
          {recent.map((s) => {
            const meta = SOURCE_TYPES[s.source_type] || { label: 'Unknown', icon: '❓' }
            return (
              <div
                key={s.session_id}
                onClick={() => navigate(`/datasets`)}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  background: 'var(--bg-tertiary)',
                  padding: '10px 14px',
                  borderRadius: 8,
                  cursor: 'pointer',
                  border: '1px solid var(--border)',
                  transition: 'border-color 0.2s',
                }}
                className="recent-row"
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: 16 }}>{meta.icon}</span>
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 700, fontFamily: 'monospace' }}>
                      {s.session_id}
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
                      {s.name || 'Unnamed'}
                    </div>
                  </div>
                </div>

                <div style={{ textAlign: 'right', fontSize: 10, color: 'var(--text-secondary)' }}>
                  <div>{s.frame_count} frames</div>
                  <div>{formatDate(s.created_at)}</div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
export { CapturePanel }
