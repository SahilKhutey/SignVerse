import { Badge } from '../shared/Badge'

export default function JobQueue({ jobs = [] }) {
  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h4 style={{ fontSize: 12, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 1 }}>
          ⚡ Active Job Queue
        </h4>
        <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
          Limit: <strong>3 concurrent</strong> | Max Heap: <strong>4096 MB</strong>
        </div>
      </div>

      {jobs.length === 0 ? (
        <p style={{ fontSize: 12, color: 'var(--text-secondary)', padding: '20px 0', ...{textAlign: 'center'} }}>
          No active background jobs processing. The queue is idle.
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
          {jobs.map((job) => {
            const statusColor = {
              queued: 'neutral',
              validating: 'processing',
              processing: 'processing',
              completed: 'ready',
              failed: 'error',
              cancelled: 'neutral',
            }[job.status] || 'neutral'

            return (
              <div
                key={job.job_id}
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
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 12, fontWeight: 700, fontFamily: 'monospace' }}>
                      {job.job_id}
                    </span>
                    <Badge status={statusColor}>{job.status.toUpperCase()}</Badge>
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 4 }}>
                    Type: {job.source_type} | RAM: {job.peak_memory_mb ? `${job.peak_memory_mb.toFixed(1)} MB` : '—'}
                  </div>
                </div>

                {job.status === 'processing' && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{
                      width: 120,
                      height: 6,
                      background: 'var(--border)',
                      borderRadius: 3,
                      overflow: 'hidden',
                    }}>
                      <div style={{
                        width: `${(job.progress || 0) * 100}%`,
                        height: '100%',
                        background: 'var(--accent)',
                      }} />
                    </div>
                    <span style={{ fontSize: 11, color: 'var(--accent)', fontWeight: 600 }}>
                      {Math.round((job.progress || 0) * 100)}%
                    </span>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
export { JobQueue }
