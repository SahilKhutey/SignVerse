import { useEffect, useState } from 'react'
import api from '../../api/client'

export default function StatusBar() {
  const [health, setHealth] = useState(null)

  useEffect(() => {
    const check = async () => {
      try {
        const { data } = await api.get('/health')
        setHealth(data)
      } catch (err) {
        setHealth({ status: 'offline' })
      }
    }
    check()
    const i = setInterval(check, 10000)
    return () => clearInterval(i)
  }, [])

  return (
    <footer style={{ 
      padding: '8px 16px', 
      background: 'var(--bg-secondary)', 
      borderTop: '1px solid var(--border)',
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      fontSize: '11px',
      color: 'var(--text-secondary)',
    }}>
      <span>
        🔌 Service Status: <strong style={{ color: health?.status === 'healthy' ? 'var(--success)' : 'var(--danger)' }}>
          {health?.status || 'checking...'}
        </strong>
      </span>
      <span>SignVerse Motion Platform</span>
      <span><a href="/docs" target="_blank" rel="noreferrer" style={{ color: 'var(--accent)', textDecoration: 'none' }}>Swagger API Docs</a></span>
    </footer>
  )
}
export { StatusBar }
