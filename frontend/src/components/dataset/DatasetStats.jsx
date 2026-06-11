export default function DatasetStats({ stats }) {
  const s = stats || {
    total_sessions: 0,
    total_frames: 0,
    labeled_sessions: 0,
    source_counts: {}
  }

  const totalSessions = s.total_sessions || 0
  const totalFrames = s.total_frames || 0
  const labeled = s.labeled_sessions || 0
  const unlabeled = Math.max(0, totalSessions - labeled)

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(4, 1fr)',
      gap: 16,
    }}>
      <StatCard label="Total Sessions" value={totalSessions} icon="📂" color="var(--accent)" />
      <StatCard label="Total Frames" value={totalFrames} icon="🎞️" color="var(--accent-2)" />
      <StatCard label="Labeled Count" value={labeled} icon="🏷️" color="var(--success)" />
      <StatCard label="Unlabeled Count" value={unlabeled} icon="⏳" color="var(--warning)" />
    </div>
  )
}

function StatCard({ label, value, icon, color }) {
  return (
    <div className="card" style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '16px 20px',
    }}>
      <div>
        <div style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 1 }}>
          {label}
        </div>
        <div style={{ fontSize: 24, fontWeight: 700, marginTop: 4, color }}>
          {value}
        </div>
      </div>
      <span style={{ fontSize: 28, opacity: 0.8 }}>{icon}</span>
    </div>
  )
}
export { DatasetStats }
