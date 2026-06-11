import { useState, useEffect } from 'react'
import axios from 'axios'

const API = '/api'

export default function MetricsDashboard() {
  const [analytics, setAnalytics] = useState(null)
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const { data } = await axios.get(`${API}/analytics/dataset`)
      setAnalytics(data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  if (loading || !analytics) {
    return <div style={{ color: 'var(--text-secondary)' }}>⏳ Loading analytics...</div>
  }

  if (analytics.empty) {
    return (
      <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
        📊 No data yet. Process a video to see analytics.
      </div>
    )
  }

  const s = analytics.summary
  const maxActionCount = Math.max(...Object.values(analytics.action_distribution || { idle: 1 }), 1)

  const ACTION_COLORS = {
    idle: '#6b7280',
    walk: '#10b981',
    wave: '#f59e0b',
    arm_raise: '#00d9ff',
    grab: '#7c3aed',
    sit: '#ec4899',
    gesture: '#3b82f6',
  }

  return (
    <div>
      <h2 style={{ fontSize: '1rem', marginBottom: '0.75rem' }}>📊 Dataset Analytics</h2>

      {/* Top metrics */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(2, 1fr)',
        gap: '8px',
        marginBottom: '1rem',
      }}>
        <MetricCard label="Sessions" value={s.total_sessions} icon="📁" />
        <MetricCard label="Total Frames" value={s.total_frames.toLocaleString()} icon="🎬" />
        <MetricCard label="Total Duration" value={`${s.total_duration_sec.toFixed(1)}s`} icon="⏱" />
        <MetricCard label="Avg Intensity" value={s.avg_motion_intensity} icon="⚡" />
      </div>

      {/* Source breakdown */}
      {s.sources && Object.keys(s.sources).length > 0 && (
        <div style={{ marginBottom: '1rem' }}>
          <h3 style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
            📡 Source Breakdown
          </h3>
          {Object.entries(s.sources).map(([src, count]) => (
            <div key={src} style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
              <span style={{ minWidth: '70px', fontSize: '0.8rem', textTransform: 'capitalize' }}>{src}</span>
              <div style={{
                flex: 1,
                height: '8px',
                background: 'var(--bg-tertiary)',
                borderRadius: '4px',
                overflow: 'hidden',
              }}>
                <div style={{
                  width: `${(count / s.total_sessions) * 100}%`,
                  height: '100%',
                  background: 'var(--accent)',
                }} />
              </div>
              <span style={{ fontSize: '0.8rem', color: 'var(--accent)', fontWeight: 600 }}>{count}</span>
            </div>
          ))}
        </div>
      )}

      {/* Action distribution */}
      {analytics.action_distribution && Object.keys(analytics.action_distribution).length > 0 && (
        <div>
          <h3 style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
            🎯 Detected Actions
          </h3>
          {Object.entries(analytics.action_distribution).map(([action, count]) => (
            <div key={action} style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
              <span style={{ minWidth: '70px', fontSize: '0.8rem', textTransform: 'capitalize' }}>{action}</span>
              <div style={{
                flex: 1,
                height: '8px',
                background: 'var(--bg-tertiary)',
                borderRadius: '4px',
                overflow: 'hidden',
              }}>
                <div style={{
                  width: `${(count / maxActionCount) * 100}%`,
                  height: '100%',
                  background: ACTION_COLORS[action] || 'var(--accent)',
                }} />
              </div>
              <span style={{ fontSize: '0.8rem', color: 'var(--accent)', fontWeight: 600 }}>{count}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function MetricCard({ label, value, icon }) {
  return (
    <div style={{
      background: 'var(--bg-tertiary)',
      padding: '10px',
      borderRadius: '8px',
      border: '1px solid var(--border)',
    }}>
      <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
        {icon} {label}
      </div>
      <div style={{ fontSize: '1.2rem', color: 'var(--accent)', fontWeight: 600, marginTop: '2px' }}>
        {value}
      </div>
    </div>
  )
}
