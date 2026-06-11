import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/auth'
import Button from '../components/shared/Button'

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const { login, loading, error } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    const success = await login(username, password)
    if (success) {
      navigate('/capture')
    }
  }

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100vh',
      background: 'var(--bg-primary)',
    }}>
      <form onSubmit={handleSubmit} style={{
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        padding: '2rem',
        width: '100%',
        maxWidth: 380,
        boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
      }}>
        <h2 style={{ fontSize: 20, color: 'var(--accent)', marginBottom: 6, textAlign: 'center' }}>🤖 SignVerse</h2>
        <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 24, textAlign: 'center' }}>
          Log in to continue to the motion intelligence console
        </p>

        {error && (
          <div style={{
            background: 'rgba(239, 68, 68, 0.15)',
            border: '1px solid var(--danger)',
            borderRadius: 6,
            padding: 10,
            fontSize: 12,
            color: 'var(--danger)',
            marginBottom: 16,
          }}>
            ❌ {error}
          </div>
        )}

        <div style={{ marginBottom: 16 }}>
          <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Username</label>
          <input
            type="text"
            className="input"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            style={{ marginTop: 0 }}
            required
          />
        </div>

        <div style={{ marginBottom: 24 }}>
          <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Password</label>
          <input
            type="password"
            className="input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={{ marginTop: 0 }}
            required
          />
        </div>

        <Button type="submit" disabled={loading} style={{ width: '100%' }}>
          {loading ? 'Logging in...' : 'Login'}
        </Button>
      </form>
    </div>
  )
}
