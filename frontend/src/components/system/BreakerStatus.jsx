import { Badge } from '../shared/Badge'
import { BREAKERS } from '../../utils/constants'

export default function BreakerStatus({ breakers }) {
  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <h4 style={{ fontSize: 12, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 1 }}>
        🛡️ Circuit Breakers
      </h4>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 8 }}>
        {BREAKERS.map((b) => {
          const state = breakers[b.id] || { state: 'closed', failure_count: 0 }
          const statusMap = {
            closed: 'ready',
            open: 'error',
            half_open: 'processing',
          }
          const badgeStatus = statusMap[state.state] || 'neutral'

          return (
            <div
              key={b.id}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                background: 'var(--bg-tertiary)',
                padding: '10px 14px',
                borderRadius: 8,
                border: '1px solid var(--border)',
              }}
            >
              <div>
                <div style={{ fontSize: 13, fontWeight: 600 }}>{b.label}</div>
                <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 2 }}>
                  Failures: <strong style={{ color: state.failure_count > 0 ? 'var(--danger)' : 'var(--text-secondary)' }}>{state.failure_count}</strong>
                </div>
              </div>
              <Badge status={badgeStatus}>
                {state.state.toUpperCase()}
              </Badge>
            </div>
          )
        })}
      </div>
    </div>
  )
}
export { BreakerStatus }
