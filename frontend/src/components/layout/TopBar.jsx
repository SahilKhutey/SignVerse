import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { useAuthStore } from '../../store/auth'
import api from '../../api/client'

const PAGE_TITLES = {
  '/capture': 'Capture Studio',
  '/live': 'Live Perception',
  '/datasets': 'Dataset Manager',
  '/viewer': '3D Viewer',
  '/export': 'Export Center',
  '/system': 'System Health',
  '/settings': 'Settings',
}

export default function TopBar() {
  const location = useLocation()
  const { user, logout } = useAuthStore()
  const [health, setHealth] = useState(null)
  const [time, setTime] = useState(new Date())
  
  useEffect(() => {
    const check = async () => {
      try {
        const { data } = await api.get('/health')
        setHealth(data)
      } catch {
        setHealth({ status: 'offline' })
      }
    }
    check()
    const i = setInterval(check, 15000)
    return () => clearInterval(i)
  }, [])
  
  useEffect(() => {
    const i = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(i)
  }, [])
  
  const title = PAGE_TITLES[location.pathname] || 'SignVerse'
  
  return (
    <header style={{
      height: 56,
      background: 'var(--bg-secondary)',
      borderBottom: '1px solid var(--border)',
      padding: '0 1.5rem',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
    }}>
      <div>
        <h2 style={{ fontSize: 16, color: 'var(--text-primary)', margin: 0 }}>{title}</h2>
        <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 2 }}>
          {time.toLocaleTimeString()}
        </div>
      </div>
      
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        {/* Health indicator */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11 }}>
          <span style={{
            width: 8, height: 8, borderRadius: '50%',
            background: health?.status === 'healthy' ? '#10b981' : '#ef4444',
            boxShadow: health?.status === 'healthy' 
              ? '0 0 8px #10b981' 
              : '0 0 8px #ef4444',
          }} />
          <span style={{ color: 'var(--text-secondary)' }}>
            {health?.status || '...'}
          </span>
        </div>
        
        {/* User menu */}
        {user && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{
              width: 32, height: 32, borderRadius: '50%',
              background: 'var(--bg-tertiary)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 12, color: 'var(--accent)', fontWeight: 600,
            }}>
              {user.user_id[0]?.toUpperCase()}
            </div>
            <button
              onClick={logout}
              style={{
                background: 'transparent',
                border: '1px solid var(--border)',
                color: 'var(--text-secondary)',
                padding: '4px 10px',
                borderRadius: 4,
                cursor: 'pointer',
                fontSize: 11,
              }}
            >
              Logout
            </button>
          </div>
        )}
      </div>
    </header>
  )
}
