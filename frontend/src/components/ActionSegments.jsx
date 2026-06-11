import { useState, useEffect } from 'react'
import axios from 'axios'

const API = '/api'

const ACTION_COLORS = {
  idle: '#6b7280',
  walk: '#10b981',
  wave: '#f59e0b',
  arm_raise: '#00d9ff',
  grab: '#7c3aed',
  sit: '#ec4899',
  gesture: '#3b82f6',
}

export default function ActionSegments({ sessionId, onSegmentClick, totalFrames = 100 }) {
  const [segments, setSegments] = useState([])
  const [loading, setLoading] = useState(false)

  const segment = async () => {
    if (!sessionId) return
    setLoading(true)
    try {
      const { data } = await axios.post(`${API}/analytics/segment`, {
        session_id: sessionId,
      })
      setSegments(data.segments)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (sessionId) {
      // Load existing segments first
      axios.get(`${API}/analytics/segments/${sessionId}`)
        .then(({ data }) => setSegments(data))
        .catch(() => {})
    }
  }, [sessionId])

  if (!sessionId) return null

  return (
    <div style={{ marginTop: '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
          🎬 Action Timeline
        </h3>
        <button
          onClick={segment}
          disabled={loading}
          className="btn btn-secondary"
          style={{ width: 'auto', padding: '4px 10px', fontSize: '0.75rem' }}
        >
          {loading ? '⏳' : '🔍'} {segments.length > 0 ? 'Re-segment' : 'Detect Actions'}
        </button>
      </div>

      {segments.length === 0 ? (
        <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
          No actions detected yet. Click "Detect Actions" to analyze.
        </p>
      ) : (
        <div style={{ marginTop: '0.5rem' }}>
          {/* Timeline bar */}
          <div style={{
            display: 'flex',
            height: '24px',
            borderRadius: '6px',
            overflow: 'hidden',
            border: '1px solid var(--border)',
            background: 'var(--bg-tertiary)',
          }}>
            {segments.map((seg, i) => {
              const segLen = (seg.end_frame - seg.start_frame + 1)
              const width = (segLen / Math.max(1, totalFrames)) * 100
              return (
                <div
                  key={i}
                  onClick={() => onSegmentClick?.(seg.start_frame)}
                  title={`${seg.action} (${seg.start_frame}-${seg.end_frame})`}
                  style={{
                    width: `${width}%`,
                    background: ACTION_COLORS[seg.action] || '#888',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '0.65rem',
                    color: 'white',
                    fontWeight: 600,
                    transition: 'opacity 0.2s',
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.opacity = '0.8'}
                  onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
                >
                  {width > 8 ? seg.action : ''}
                </div>
              )
            })}
          </div>

          {/* Segment list */}
          <div style={{ marginTop: '0.5rem', maxHeight: '150px', overflowY: 'auto' }}>
            {segments.map((seg, i) => (
              <div
                key={i}
                onClick={() => onSegmentClick?.(seg.start_frame)}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  padding: '6px 8px',
                  fontSize: '0.75rem',
                  borderBottom: '1px solid var(--border)',
                  cursor: 'pointer',
                  transition: 'background 0.2s',
                }}
                className="segment-row"
              >
                <span>
                  <span style={{
                    display: 'inline-block',
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    background: ACTION_COLORS[seg.action] || '#888',
                    marginRight: '6px',
                  }} />
                  {seg.action}
                </span>
                <span style={{ color: 'var(--text-secondary)' }}>
                  f{seg.start_frame}-{seg.end_frame} · {(seg.confidence * 100).toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
