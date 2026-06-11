import { useEffect, useState } from 'react'
import axios from 'axios'

export default function StatusBar() {
  const [health, setHealth] = useState(null)

  useEffect(() => {
    const check = async () => {
      try {
        const res = await axios.get('/health')
        setHealth(res.data)
      } catch (err) {
        setHealth({ status: 'offline' })
      }
    }
    check()
    const i = setInterval(check, 10000)
    return () => clearInterval(i)
  }, [])

  return (
    <div style={{ 
      marginTop: '2rem', 
      padding: '1rem', 
      background: 'var(--bg-secondary)', 
      borderRadius: '8px',
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      fontSize: '0.85rem',
      color: 'var(--text-secondary)',
      border: '1px solid var(--border)'
    }}>
      <span>
        🔌 API Connection: <strong style={{ color: health?.status === 'healthy' ? 'var(--success)' : 'var(--danger)' }}>
          {health?.status || 'offline'}
        </strong>
      </span>
      <span>📅 Day 1 · Foundation & Perception</span>
      <span>📖 <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer" style={{ color: 'var(--accent)', textDecoration: 'none' }}>Swagger Docs</a></span>
    </div>
  )
}
