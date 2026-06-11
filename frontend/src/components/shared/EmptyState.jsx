export function EmptyState({ icon = '📭', title, description, action = null }) {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '3rem 2rem',
      color: 'var(--text-secondary)',
      textAlign: 'center',
    }}>
      <div style={{ fontSize: '3rem', marginBottom: '0.75rem', opacity: 0.5 }}>{icon}</div>
      <h3 style={{ color: 'var(--text-primary)', marginBottom: '0.5rem', fontSize: 16 }}>{title}</h3>
      {description && <p style={{ fontSize: 13, maxWidth: 400 }}>{description}</p>}
      {action && <div style={{ marginTop: 16 }}>{action}</div>}
    </div>
  )
}
