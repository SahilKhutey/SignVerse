export function Badge({ status = 'neutral', children, size = 'md' }) {
  const colors = {
    ready: { bg: 'rgba(16, 185, 129, 0.15)', fg: '#10b981' },
    processing: { bg: 'rgba(245, 158, 11, 0.15)', fg: '#f59e0b' },
    error: { bg: 'rgba(239, 68, 68, 0.15)', fg: '#ef4444' },
    connected: { bg: 'rgba(16, 185, 129, 0.15)', fg: '#10b981' },
    disconnected: { bg: 'rgba(107, 114, 128, 0.15)', fg: '#9ca3c4' },
    neutral: { bg: 'var(--bg-tertiary)', fg: 'var(--text-secondary)' },
  }
  const c = colors[status] || colors.neutral
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 4,
      padding: size === 'sm' ? '2px 8px' : '4px 10px',
      background: c.bg,
      color: c.fg,
      borderRadius: 12,
      fontSize: size === 'sm' ? 10 : 11,
      fontWeight: 600,
    }}>
      {children}
    </span>
  )
}
