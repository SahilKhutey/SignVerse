import { useEffect, useState } from 'react'
import api from '../api/client'
import BreakerStatus from '../components/system/BreakerStatus'
import BusStats from '../components/system/BusStats'
import JobQueue from '../components/system/JobQueue'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'

export default function SystemPage() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  const fetchStats = async () => {
    try {
      const { data } = await api.get('/api/system/stats')
      setStats(data)
    } catch (err) {
      console.error('Failed to fetch system stats:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStats()
    const timer = setInterval(fetchStats, 3000)
    return () => clearInterval(timer)
  }, [])

  if (loading && !stats) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '80vh' }}>
        <LoadingSpinner size={32} message="Loading system operational status..." />
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, padding: 20 }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        {/* Left Column: Circuit Breakers */}
        <BreakerStatus breakers={stats?.breakers || {}} />

        {/* Right Column: Message Bus */}
        <BusStats bus={stats?.bus || {}} />
      </div>

      {/* Full Width Middle: Job Queue */}
      <JobQueue jobs={stats?.jobs || []} />

      {/* Full Width Bottom: Profiling Panel */}
      <ProfilingPanel />
    </div>
  )
}

function ProfilingPanel() {
  const [summary, setSummary] = useState(null)
  const [timeline, setTimeline] = useState([])
  const [components, setComponents] = useState([])
  const [alerts, setAlerts] = useState([])
  const [refreshing, setRefreshing] = useState(false)
  
  const fetchData = async () => {
    setRefreshing(true)
    try {
      const [sumRes, tlRes, compRes, alertRes] = await Promise.all([
        api.get('/api/profiling/memory/summary'),
        api.get('/api/profiling/memory/timeline?last_n=60'),
        api.get('/api/profiling/memory/components'),
        api.get('/api/profiling/memory/alerts?since_seconds=3600'),
      ])
      setSummary(sumRes.data)
      setTimeline(tlRes.data)
      setComponents(compRes.data)
      setAlerts(alertRes.data)
    } catch (e) {
      console.error('Failed to fetch profiling data:', e)
    } finally {
      setRefreshing(false)
    }
  }
  
  useEffect(() => {
    fetchData()
    const i = setInterval(fetchData, 10000)  // Refresh every 10s
    return () => clearInterval(i)
  }, [])
  
  const triggerGC = async () => {
    try {
      const { data } = await api.post('/api/profiling/memory/gc')
      alert(`Garbage Collection forced!\nFreed ${data.freed_mb.toFixed(1)} MB (${data.objects_collected} objects collected).`)
      fetchData()
    } catch (e) {
      alert('Failed to force garbage collection.')
    }
  }
  
  return (
    <div style={{
      background: 'var(--bg-secondary)',
      padding: 20,
      borderRadius: 12,
      border: '1px solid var(--border)',
      display: 'flex',
      flexDirection: 'column',
      gap: 16
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ fontSize: 18, margin: 0, color: '#00d9ff', fontFamily: 'monospace' }}>📊 Memory Profiling & diagnostics</h2>
        <div style={{ display: 'flex', gap: 10 }}>
          <button 
            onClick={triggerGC} 
            style={{
              background: '#ef4444',
              color: 'white',
              border: 'none',
              padding: '6px 12px',
              borderRadius: 6,
              cursor: 'pointer',
              fontWeight: 'bold',
              fontSize: 12,
            }}
          >
            🗑 Force GC
          </button>
          <button 
            onClick={fetchData} 
            disabled={refreshing} 
            style={{
              background: '#00d9ff',
              color: '#0a0e27',
              border: 'none',
              padding: '6px 12px',
              borderRadius: 6,
              cursor: 'pointer',
              fontWeight: 'bold',
              fontSize: 12,
            }}
          >
            {refreshing ? '⏳ Loading...' : '🔄 Refresh'}
          </button>
        </div>
      </div>
      
      {summary && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
          <MetricCard 
            label="Current RSS Memory" 
            value={`${summary.process?.rss_mb?.current?.toFixed(1) || 0} MB`}
            color={summary.process?.rss_mb?.current > 2048 ? '#ef4444' : '#10b981'}
          />
          <MetricCard 
            label="Peak RSS Memory" 
            value={`${summary.process?.rss_mb?.max?.toFixed(1) || 0} MB`}
          />
          <MetricCard 
            label="Mean CPU Utilization" 
            value={`${summary.process?.cpu_percent?.mean?.toFixed(1) || 0}%`}
          />
          <MetricCard 
            label="Alerts (Last 1h)" 
            value={summary.alerts?.recent || 0}
            color={summary.alerts?.recent > 0 ? '#f59e0b' : '#9ca3c4'}
          />
        </div>
      )}
      
      {/* Timeline chart */}
      <div style={{ background: '#0a0e27', padding: 16, borderRadius: 8, border: '1px solid var(--border)' }}>
        <h3 style={{ fontSize: 13, margin: '0 0 12px 0', color: '#9ca3c4', fontFamily: 'monospace' }}>Memory Timeline (Last 5 min)</h3>
        <MemoryTimelineChart data={timeline} />
      </div>
      
      {/* Components */}
      <div style={{ background: '#0a0e27', padding: 16, borderRadius: 8, border: '1px solid var(--border)' }}>
        <h3 style={{ fontSize: 13, margin: '0 0 12px 0', color: '#9ca3c4', fontFamily: 'monospace' }}>Tracked Components Memory Usage</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {components.length === 0 ? (
            <div style={{ color: '#9ca3c4', fontSize: 12 }}>No components tracked yet. Submit a motion analysis job to profile.</div>
          ) : (
            components.map(c => (
              <div key={c.name} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, fontFamily: 'monospace' }}>
                  <span style={{ color: '#e2e8f0' }}>{c.name} ({c.component_type})</span>
                  <span style={{ color: '#00d9ff' }}>
                    {c.current_mb.toFixed(1)} MB / Peak: {c.peak_mb.toFixed(1)} MB
                  </span>
                </div>
                <div style={{ height: 6, background: '#1e293b', borderRadius: 3, overflow: 'hidden' }}>
                  <div style={{
                    width: `${Math.min(100, (c.peak_mb / 2048) * 100)}%`,
                    height: '100%',
                    background: c.peak_mb > 1024 ? '#ef4444' : '#00d9ff',
                    borderRadius: 3,
                    transition: 'width 0.3s ease'
                  }} />
                </div>
              </div>
            ))
          )}
        </div>
      </div>
      
      {/* Alerts */}
      {alerts.length > 0 && (
        <div style={{ background: '#0a0e27', padding: 16, borderRadius: 8, border: '1px solid #ef4444' }}>
          <h3 style={{ fontSize: 13, margin: '0 0 12px 0', color: '#ef4444', fontFamily: 'monospace' }}>⚠️ Memory Leak Alerts</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {alerts.map((a, idx) => (
              <div key={idx} style={{
                padding: 10,
                background: a.severity === 'CRITICAL' ? 'rgba(239, 68, 68, 0.1)' : 'rgba(245, 158, 11, 0.1)',
                borderLeft: `3px solid ${a.severity === 'CRITICAL' ? '#ef4444' : '#f59e0b'}`,
                borderRadius: 4,
                fontSize: 12,
                fontFamily: 'monospace',
                color: '#e2e8f0'
              }}>
                <strong>{a.type}</strong> · {a.severity}
                <div style={{ marginTop: 4 }}>{a.message}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function MetricCard({ label, value, color = '#00d9ff' }) {
  return (
    <div style={{
      background: '#0a0e27',
      padding: 16,
      borderRadius: 8,
      border: '1px solid var(--border)',
    }}>
      <div style={{ fontSize: 11, color: '#9ca3c4', fontFamily: 'monospace', textTransform: 'uppercase' }}>{label}</div>
      <div style={{ fontSize: 24, color, fontWeight: 'bold', marginTop: 4, fontFamily: 'monospace' }}>{value}</div>
    </div>
  )
}

function MemoryTimelineChart({ data }) {
  if (!data || data.length < 2) {
    return <div style={{ color: '#9ca3c4', fontSize: 12, fontFamily: 'monospace' }}>Collecting system timeline data...</div>
  }
  
  const maxMB = Math.max(...data.map(d => d.rss_mb))
  const minMB = Math.min(...data.map(d => d.rss_mb))
  const range = maxMB - minMB || 1
  
  const width = 800
  const height = 120
  
  const points = data.map((d, i) => {
    const x = (i / (data.length - 1)) * width
    const y = height - 10 - ((d.rss_mb - minMB) / range) * (height - 20)
    return `${x},${y}`
  }).join(' ')
  
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} style={{ background: '#0a0e27', borderRadius: 4 }}>
        <polyline
          points={points}
          fill="none"
          stroke="#00d9ff"
          strokeWidth="2"
        />
        {/* Draw subtle grid lines */}
        <line x1="0" y1="10" x2={width} y2="10" stroke="#1e293b" strokeDasharray="3,3" />
        <line x1="0" y1={height - 10} x2={width} y2={height - 10} stroke="#1e293b" strokeDasharray="3,3" />
      </svg>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#9ca3c4', fontFamily: 'monospace' }}>
        <span>Min: {minMB.toFixed(1)} MB</span>
        <span>Max: {maxMB.toFixed(1)} MB</span>
      </div>
    </div>
  )
}

export { SystemPage }
