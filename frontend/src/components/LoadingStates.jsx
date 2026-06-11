export function SkeletonLoader({ height = 200 }) {
  return (
    <div style={{
      height,
      background: 'linear-gradient(90deg, var(--bg-tertiary) 0%, var(--bg-secondary) 50%, var(--bg-tertiary) 100%)',
      backgroundSize: '200% 100%',
      animation: 'shimmer 1.5s infinite',
      borderRadius: '8px',
    }}>
      <style>{`
        @keyframes shimmer {
          0% { background-position: -200% 0; }
          100% { background-position: 200% 0; }
        }
      `}</style>
    </div>
  )
}

export function Spinner({ size = 24 }) {
  return (
    <div style={{
      width: size,
      height: size,
      border: `3px solid var(--bg-tertiary)`,
      borderTopColor: 'var(--accent)',
      borderRadius: '50%',
      animation: 'spin 0.8s linear infinite',
      display: 'inline-block',
    }}>
      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}

export function EmptyState({ icon = '📭', title, description }) {
  return (
    <div style={{
      textAlign: 'center',
      padding: '2rem',
      color: 'var(--text-secondary)',
    }}>
      <div style={{ fontSize: '3rem', marginBottom: '0.5rem' }}>{icon}</div>
      <h3 style={{ color: 'var(--text-primary)', marginBottom: '0.5rem', fontSize: '1rem' }}>{title}</h3>
      <p style={{ fontSize: '0.85rem' }}>{description}</p>
    </div>
  )
}
