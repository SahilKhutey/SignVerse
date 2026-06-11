import { useEffect, useState, useRef } from 'react'
import api from '../api/client'

const TYPE_CONFIG = {
  NO_CONTACT:   { color: 'transparent', label: 'None',        height: 0  },
  APPROACHING:  { color: '#4488ff',     label: 'Approaching', height: 12 },
  NEAR:         { color: '#ffcc00',     label: 'Near',        height: 14 },
  TOUCHING:     { color: '#ff8800',     label: 'Touching',    height: 16 },
  GRASPING:     { color: '#ff4400',     label: 'Grasping',    height: 18 },
  HOLDING:      { color: '#00e676',     label: 'Holding',     height: 20 },
  LIFTING:      { color: '#00e5ff',     label: 'Lifting',     height: 20 },
  MOVING:       { color: '#7c4dff',     label: 'Moving',      height: 20 },
  PLACING:      { color: '#ff6d00',     label: 'Placing',     height: 18 },
  RELEASING:    { color: '#e040fb',     label: 'Releasing',   height: 16 },
  POINTING:     { color: '#40c4ff',     label: 'Pointing',    height: 14 },
  USING:        { color: '#69f0ae',     label: 'Using',       height: 18 },
  MANIPULATING: { color: '#ffab40',     label: 'Manipulating',height: 18 },
}

const CLASS_COLORS = [
  '#00e5ff', '#69f0ae', '#ff6d00', '#e040fb',
  '#ffca28', '#40c4ff', '#ff4081', '#b9f6ca',
  '#ea80fc', '#ff8a65', '#82b1ff', '#ccff90',
]

export default function InteractionTimeline({ sessionId }) {
  const [timeline, setTimeline] = useState(null)
  const [objects,  setObjects]  = useState(null)
  const [stats,    setStats]    = useState(null)
  const [loading,  setLoading]  = useState(true)
  const [hoveredEvent, setHoveredEvent] = useState(null)
  const [currentFrame, setCurrentFrame] = useState(0)
  const containerRef = useRef(null)

  useEffect(() => {
    if (!sessionId) return
    setLoading(true)
    Promise.all([
      api.get(`/api/hoi/${sessionId}/timeline?min_confidence=0.4`),
      api.get(`/api/hoi/${sessionId}/objects`),
      api.get(`/api/hoi/${sessionId}/stats`),
    ])
      .then(([tl, ob, st]) => {
        setTimeline(tl.data)
        setObjects(ob.data)
        setStats(st.data)
      })
      .catch(() => {
        setTimeline({ events: [], total_events: 0 })
        setObjects({ objects: [], unique_classes: [] })
        setStats(null)
      })
      .finally(() => setLoading(false))
  }, [sessionId])

  if (!sessionId) return (
    <div style={{ color: 'var(--text-secondary)', fontSize: 12, padding: '1rem', textAlign: 'center' }}>
      Select a session to view interaction timeline
    </div>
  )

  if (loading) return (
    <div style={{ color: 'var(--text-secondary)', fontSize: 12, padding: '1rem', textAlign: 'center' }}>
      Loading interaction data…
    </div>
  )

  const events    = timeline?.events || []
  const objList   = objects?.objects || []
  const totalFrames = stats?.frame_count || 1

  // Group events by (object_track_id + hand) for track rows
  const tracks = {}
  for (const ev of events) {
    const key = `${ev.hand}:${ev.object_track_id}:${ev.object_class}`
    if (!tracks[key]) tracks[key] = { hand: ev.hand, class: ev.object_class, tid: ev.object_track_id, events: [] }
    tracks[key].events.push(ev)
  }
  const trackList = Object.values(tracks)

  const trackColors = {}
  trackList.forEach((t, i) => {
    trackColors[`${t.hand}:${t.tid}`] = CLASS_COLORS[i % CLASS_COLORS.length]
  })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '0.5rem' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ fontSize: 14, fontWeight: 600 }}>🕹 Interaction Timeline</div>
        <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
          {events.length} events · {objList.length} objects
        </div>
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 8px' }}>
        {Object.entries(TYPE_CONFIG).filter(([,v]) => v.height > 0).map(([type, cfg]) => (
          <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 9, color: 'var(--text-secondary)' }}>
            <div style={{ width: 8, height: 8, borderRadius: 2, background: cfg.color }} />
            {cfg.label}
          </div>
        ))}
      </div>

      {/* Stats pills */}
      {stats && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {stats.unique_objects?.map(cls => (
            <span key={cls} style={{
              fontSize: 10, padding: '2px 8px', borderRadius: 10,
              background: 'rgba(0,217,255,0.08)', border: '1px solid rgba(0,217,255,0.15)',
              color: 'var(--accent)',
            }}>
              {cls}
            </span>
          ))}
          {stats.total_hoi_events > 0 && (
            <span style={{ fontSize: 10, color: 'var(--text-secondary)', padding: '2px 6px' }}>
              {stats.total_hoi_events} total interactions
            </span>
          )}
        </div>
      )}

      {/* Timeline canvas */}
      {trackList.length === 0 ? (
        <div style={{
          padding: '1.5rem', textAlign: 'center', fontSize: 12,
          color: 'var(--text-secondary)',
          background: 'var(--bg-tertiary)', borderRadius: 8,
          border: '1px solid var(--border)',
        }}>
          No hand-object interactions detected in this session.<br/>
          <span style={{ fontSize: 10, opacity: 0.6 }}>
            Interactions are captured when hands are near manipulable objects.
          </span>
        </div>
      ) : (
        <div
          ref={containerRef}
          style={{
            background: 'var(--bg-tertiary)',
            border: '1px solid var(--border)',
            borderRadius: 8,
            overflow: 'hidden',
            position: 'relative',
          }}
        >
          {trackList.map((track, ti) => {
            const trackKey = `${track.hand}:${track.tid}`
            const color = trackColors[trackKey]
            return (
              <div key={trackKey} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                {/* Track label */}
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  padding: '4px 8px', fontSize: 10,
                  background: 'rgba(0,0,0,0.2)',
                }}>
                  <div style={{ width: 8, height: 8, borderRadius: 2, background: color }} />
                  <span style={{ color, fontWeight: 600 }}>{track.class}</span>
                  <span style={{ color: 'var(--text-secondary)' }}>#{track.tid}</span>
                  <span style={{ marginLeft: 4, color: 'rgba(255,255,255,0.3)', fontSize: 9 }}>
                    {track.hand} hand
                  </span>
                </div>
                {/* Events bar */}
                <div style={{ position: 'relative', height: 28, cursor: 'pointer' }}>
                  {track.events.map((ev, ei) => {
                    const left = `${(ev.frame_id / totalFrames) * 100}%`
                    const width = `${Math.max((ev.duration_frames / totalFrames) * 100, 0.4)}%`
                    const cfg = TYPE_CONFIG[ev.interaction_type] || TYPE_CONFIG.NEAR
                    return (
                      <div
                        key={ei}
                        title={`${ev.interaction_type} — ${ev.object_class}\nFrame ${ev.frame_id}, ${ev.duration_frames} frames\nConfidence: ${(ev.confidence*100).toFixed(0)}%`}
                        onMouseEnter={() => setHoveredEvent(ev)}
                        onMouseLeave={() => setHoveredEvent(null)}
                        style={{
                          position: 'absolute',
                          left, width,
                          top: `${(28 - cfg.height) / 2}px`,
                          height: `${cfg.height}px`,
                          background: cfg.color,
                          borderRadius: 3,
                          opacity: 0.85,
                          transition: 'opacity 0.1s',
                          zIndex: 1,
                        }}
                      />
                    )
                  })}
                  {/* Playhead */}
                  <div style={{
                    position: 'absolute', top: 0, bottom: 0,
                    left: `${(currentFrame / totalFrames) * 100}%`,
                    width: 1, background: 'rgba(255,255,255,0.4)',
                    pointerEvents: 'none', zIndex: 2,
                  }} />
                </div>
              </div>
            )
          })}

          {/* Frame ruler */}
          <div style={{
            display: 'flex', justifyContent: 'space-between',
            padding: '2px 8px', fontSize: 9, color: 'rgba(255,255,255,0.2)',
            background: 'rgba(0,0,0,0.3)',
          }}>
            <span>Frame 0</span>
            <span>Frame {Math.floor(totalFrames / 2)}</span>
            <span>Frame {totalFrames}</span>
          </div>
        </div>
      )}

      {/* Hover tooltip */}
      {hoveredEvent && (
        <div style={{
          background: 'var(--bg-secondary)', border: '1px solid var(--border)',
          borderRadius: 8, padding: '8px 12px', fontSize: 11,
          boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
        }}>
          <div style={{ fontWeight: 600, color: TYPE_CONFIG[hoveredEvent.interaction_type]?.color || '#fff' }}>
            {TYPE_CONFIG[hoveredEvent.interaction_type]?.label} — {hoveredEvent.object_class}
          </div>
          <div style={{ color: 'var(--text-secondary)', marginTop: 4 }}>
            Frame {hoveredEvent.frame_id} · {hoveredEvent.duration_frames} frames · {hoveredEvent.hand} hand
          </div>
          <div style={{ color: 'var(--text-secondary)' }}>
            Confidence: {((hoveredEvent.confidence || 0) * 100).toFixed(0)}%
            {hoveredEvent.distance_3d ? ` · Distance: ${hoveredEvent.distance_3d.toFixed(2)}m` : ''}
          </div>
        </div>
      )}

      {/* Hold durations */}
      {stats?.hold_statistics && Object.keys(stats.hold_statistics).length > 0 && (
        <div style={{
          background: 'var(--bg-tertiary)', border: '1px solid var(--border)',
          borderRadius: 8, padding: '8px',
        }}>
          <div style={{ fontSize: 10, fontWeight: 600, marginBottom: 6, color: '#00e676' }}>
            Hold Events
          </div>
          {Object.entries(stats.hold_statistics).map(([cls, hs]) => (
            <div key={cls} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, marginBottom: 3 }}>
              <span style={{ color: 'var(--text-primary)' }}>{cls}</span>
              <span style={{ color: 'var(--text-secondary)' }}>
                {hs.hold_count}× · max {hs.max_hold_frames}f · avg {hs.avg_hold_frames}f
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
