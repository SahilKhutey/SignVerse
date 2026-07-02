import { NavLink } from 'react-router-dom'
import { useLiveStore } from '../../store/live'

const NAV = [
  { path: '/capture', label: 'Capture', icon: '🎥' },
  { path: '/live', label: 'Live View', icon: '📡' },
  { path: '/datasets', label: 'Datasets', icon: '📂' },
  { path: '/viewer', label: '3D Viewer', icon: '🌐' },
  { path: '/export', label: 'Export', icon: '📦' },
  { path: '/system', label: 'System', icon: '⚙️' },
  { path: '/settings', label: 'Settings', icon: '🛠️' },
  { path: 'http://localhost:8501', label: 'Streamlit Studio', icon: '🎨', external: true }
]

export default function Sidebar() {
  const liveStatus = useLiveStore(s => s.status)
  const isLive = liveStatus === 'connected'
  
  return (
    <aside style={{
      width: 220,
      background: 'var(--bg-secondary)',
      borderRight: '1px solid var(--border)',
      padding: '1.25rem 0.75rem',
      display: 'flex',
      flexDirection: 'column',
      flexShrink: 0,
    }}>
      {/* Logo */}
      <div style={{ padding: '0 0.75rem', marginBottom: '1.5rem' }}>
        <h1 style={{ fontSize: '1.1rem', color: 'var(--accent)', margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
          🤖 SignVerse
        </h1>
        <p style={{ fontSize: 10, color: 'var(--text-secondary)', margin: '2px 0 0 0' }}>
          Motion Intelligence Platform
        </p>
      </div>
      
      {/* Nav */}
      <nav style={{ flex: 1 }}>
        {NAV.map(item => {
          if (item.external) {
            return (
              <a
                key={item.path}
                href={item.path}
                target="_blank"
                rel="noreferrer"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '10px 12px',
                  borderRadius: 6,
                  color: 'var(--text-secondary)',
                  textDecoration: 'none',
                  marginBottom: 2,
                  fontSize: 13,
                  transition: 'all 0.15s',
                }}
                onMouseEnter={(e) => e.currentTarget.style.color = 'var(--accent)'}
                onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-secondary)'}
              >
                <span style={{ fontSize: 16 }}>{item.icon}</span>
                <span style={{ flex: 1 }}>{item.label}</span>
                <span style={{ fontSize: 10, opacity: 0.6 }}>↗</span>
              </a>
            )
          }
          return (
            <NavLink
              key={item.path}
              to={item.path}
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '10px 12px',
                borderRadius: 6,
                color: isActive ? 'var(--accent)' : 'var(--text-secondary)',
                background: isActive ? 'var(--bg-tertiary)' : 'transparent',
                textDecoration: 'none',
                marginBottom: 2,
                fontSize: 13,
                fontWeight: isActive ? 600 : 400,
                transition: 'all 0.15s',
                position: 'relative',
              })}
            >
              <span style={{ fontSize: 16 }}>{item.icon}</span>
              <span style={{ flex: 1 }}>{item.label}</span>
              {item.path === '/live' && isLive && (
                <span style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: '#10b981',
                  boxShadow: '0 0 8px #10b981',
                  animation: 'pulse 1.5s infinite',
                }} />
              )}
            </NavLink>
          )
        })}
      </nav>
      
      {/* Footer */}
      <div style={{
        padding: '0.75rem',
        background: 'var(--bg-tertiary)',
        borderRadius: 6,
        fontSize: 10,
        color: 'var(--text-secondary)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span>Status</span>
          <span style={{ color: isLive ? '#10b981' : 'var(--text-secondary)' }}>
            {isLive ? '● Live' : '○ Idle'}
          </span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span>Version</span>
          <span>v1.0.0</span>
        </div>
      </div>
      
      <style>{`@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }`}</style>
    </aside>
  )
}
