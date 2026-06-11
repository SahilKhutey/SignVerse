export default function BusStats({ bus }) {
  const b = bus || {
    messages_published: 0,
    messages_delivered: 0,
    messages_failed: 0,
    messages_dead_lettered: 0,
    topics: [],
    subscribers_per_topic: {},
    queue_sizes: {},
    dead_letter_count: 0
  }

  const published = b.messages_published || 0
  const delivered = b.messages_delivered || 0
  const dlq = b.dead_letter_count || 0
  const topicsCount = b.topics?.length || 0

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <h4 style={{ fontSize: 12, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 1 }}>
        📡 Message Bus Dispatcher
      </h4>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 8 }}>
        <StatRow label="Published" value={published} color="var(--accent)" />
        <StatRow label="Delivered" value={delivered} color="var(--success)" />
        <StatRow label="Dead Letters" value={dlq} color={dlq > 0 ? 'var(--danger)' : 'var(--text-secondary)'} />
        <StatRow label="Topics Active" value={topicsCount} color="var(--accent-2)" />
      </div>

      <div style={{ marginTop: 12 }}>
        <h5 style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 8 }}>QUEUE SIZES & SUBSCRIBERS</h5>
        {!b.topics || b.topics.length === 0 ? (
          <p style={{ fontSize: 11, color: 'var(--text-secondary)' }}>No active topics</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 120, overflowY: 'auto' }}>
            {b.topics.map(topic => (
              <div 
                key={topic} 
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  background: 'var(--bg-tertiary)',
                  padding: '6px 10px',
                  borderRadius: 6,
                  fontSize: 11,
                  fontFamily: 'monospace',
                }}
              >
                <span style={{ color: 'var(--text-primary)' }}>{topic}</span>
                <span style={{ color: 'var(--text-secondary)' }}>
                  subs: {b.subscribers_per_topic?.[topic] || 0} | size: {b.queue_sizes?.[topic] || 0}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function StatRow({ label, value, color }) {
  return (
    <div style={{ background: 'var(--bg-tertiary)', padding: 10, borderRadius: 8, ...{textAlign: 'center'} }}>
      <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700, marginTop: 2, color }}>{value}</div>
    </div>
  )
}
export { BusStats }
