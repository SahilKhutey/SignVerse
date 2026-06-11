export function LoadingSpinner({ size = 24, message = null }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
      <div style={{
        width: size,
        height: size,
        border: `3px solid var(--bg-tertiary)`,
        borderTopColor: 'var(--accent)',
        borderRadius: '50%',
        animation: 'spin 0.8s linear infinite',
      }} />
      {message && <div style={{ color: 'var(--text-secondary)', fontSize: 13 }}>{message}</div>}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
