export default function FormatCard({ format, onClick }) {
  return (
    <div 
      onClick={onClick}
      style={{
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border)',
        borderRadius: 10,
        padding: 16,
        cursor: 'pointer',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        transition: 'all 0.2s',
      }}
      className="format-card"
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 20 }}>{format.icon}</span>
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
            {format.label}
          </span>
        </div>
        <span style={{ fontSize: 10, color: 'var(--accent)', fontWeight: 600, fontFamily: 'monospace' }}>
          {format.ext}
        </span>
      </div>

      <p style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.4 }}>
        {format.desc}
      </p>

      <div style={{
        marginTop: 4,
        alignSelf: 'flex-end',
        fontSize: 11,
        color: 'var(--accent)',
        fontWeight: 600,
      }}>
        Download ⬇️
      </div>
    </div>
  )
}
export { FormatCard }
