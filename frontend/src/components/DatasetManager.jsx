import { useEffect, useState, useRef } from 'react'
import { useMotionStore } from '../store/motionStore'
import api from '../api/client'

const LABELS = ['GESTURE', 'WALK', 'SIT_STAND', 'IDLE', 'WAVE', 'PICK_UP', 'CUSTOM']

// ─── Format definitions ─────────────────────────────────────────────────── //
const EXPORT_FORMATS = [
  // 3D Animation (person-only)
  { id: 'bvh',          label: 'BVH',             icon: '🎭', cat: '3D',      ext: '.bvh',  tip: 'Blender, Maya, MotionBuilder',    scene: false },
  { id: 'fbx',          label: 'FBX',             icon: '🎮', cat: '3D',      ext: '.fbx',  tip: 'Unity, Unreal, Maya, Blender',    scene: false },
  { id: 'gltf',         label: 'GLTF 2.0',        icon: '🌐', cat: 'Web',     ext: '.gltf', tip: 'Three.js, Babylon.js, ARCore',    scene: false },
  { id: 'glb',          label: 'GLB',             icon: '📦', cat: 'Web',     ext: '.glb',  tip: 'Binary GLTF — web & AR platforms', scene: false },
  // Robotics
  { id: 'mujoco',       label: 'MuJoCo XML',      icon: '🤖', cat: 'Robot',   ext: '.xml',  tip: 'MuJoCo, MuJoCo MPC, dm_control',  scene: false },
  { id: 'urdf',         label: 'URDF',            icon: '🔩', cat: 'Robot',   ext: '.urdf', tip: 'ROS, Gazebo, Isaac Sim',           scene: false },
  { id: 'ros2',         label: 'ROS2 Traj.',      icon: '📡', cat: 'Robot',   ext: '.yaml', tip: 'ROS2 Humble / Iron / Jazzy',       scene: false },
  { id: 'pinocchio',    label: 'Pinocchio',       icon: '⚙️', cat: 'Robot',   ext: '.json', tip: 'Pinocchio, TSID, OCS2',            scene: false },
  // Data / Script
  { id: 'csv',          label: 'CSV',             icon: '📊', cat: 'Data',    ext: '.csv',  tip: 'Pandas, MATLAB, Excel',            scene: false },
  { id: 'blender',      label: 'Blender Script',  icon: '🍊', cat: 'Script',  ext: '.py',   tip: 'Blender 3.x / 4.x headless',      scene: false },
  { id: 'json',         label: 'SignVerse JSON',  icon: '📋', cat: 'Data',    ext: '.json', tip: 'Full session data (raw)',           scene: false },
  // Metric Data
  { id: 'metric_json',  label: 'Metric JSON',     icon: '📏', cat: 'Metric',  ext: '.json', tip: '3D coordinates in meters',       scene: false },
  { id: 'metric_csv',   label: 'Metric CSV',      icon: '📈', cat: 'Metric',  ext: '.csv',  tip: '3D coordinate time series in meters', scene: false },
  { id: 'measurements_csv', label: 'Biomech CSV',  icon: '🦴', cat: 'Metric',  ext: '.csv',  tip: 'Anthropometric stats over time',   scene: false },
  // ── Scene-level (person + objects) ──────────────────────────────
  { id: 'gltf_scene',   label: 'GLTF Scene',      icon: '🎬', cat: 'Scene',   ext: '.gltf', tip: 'Person + Objects — Three.js, Babylon', scene: true },
  { id: 'glb_scene',    label: 'GLB Scene',       icon: '🎬', cat: 'Scene',   ext: '.glb',  tip: 'Binary scene — Web, Unity, Unreal',    scene: true },
  { id: 'bvh_scene',    label: 'BVH Scene',       icon: '🏃', cat: 'Scene',   ext: '.bvh',  tip: 'Person + Object joints — Blender',     scene: true },
  { id: 'mujoco_scene', label: 'MuJoCo Scene',    icon: '🦾', cat: 'Scene',   ext: '.xml',  tip: 'Full scene RL — MuJoCo, IsaacGym',     scene: true },
  { id: 'usd_scene',    label: 'USD Scene',       icon: '🌌', cat: 'Scene',   ext: '.usda', tip: 'USD ASCII — Houdini, Unreal, Omniverse',scene: true },
]

const CAT_COLORS = {
  '3D':     'rgba(124, 58, 237, 0.18)',
  'Web':    'rgba(0, 196, 255, 0.15)',
  'Robot':  'rgba(0, 255, 128, 0.13)',
  'Data':   'rgba(255, 160, 0, 0.13)',
  'Script': 'rgba(255, 80, 80, 0.13)',
  'Scene':  'rgba(255, 180, 0, 0.16)',
  'Metric': 'rgba(244, 63, 94, 0.15)',
}

const CAT_BORDER = {
  '3D':     '#7c3aed',
  'Web':    '#00c4ff',
  'Robot':  '#00ff80',
  'Data':   '#ffa000',
  'Script': '#ff5050',
  'Scene':  '#ffb300',
  'Metric': '#f43f5e',
}

export default function DatasetManager() {
  const sessions       = useMotionStore(s => s.sessions)
  const selectedSession = useMotionStore(s => s.selectedSession)
  const fetchSessions  = useMotionStore(s => s.fetchSessions)
  const selectSession  = useMotionStore(s => s.selectSession)
  const deleteSession  = useMotionStore(s => s.deleteSession)
  const loading        = useMotionStore(s => s.loading)

  useEffect(() => { fetchSessions() }, [])

  const handleDelete = async (id) => {
    if (!confirm('Delete this session?')) return
    await deleteSession(id)
  }

  const handleLabel = async (id, label) => {
    await api.patch(`/api/sessions/${id}/label`, { label })
    fetchSessions()
    if (selectedSession?.session_id === id) selectSession(id)
  }

  const handleExport = async (id, fmt, ext) => {
    try {
      const res = await api.get(`/api/exporters/${id}/export?format=${fmt}`, { responseType: 'blob' })
      const a = document.createElement('a')
      a.href = URL.createObjectURL(res.data)
      a.download = `session_${id.slice(0, 8)}${ext}`
      a.click()
      URL.revokeObjectURL(a.href)
    } catch (err) {
      alert(`Export failed: ${err?.response?.data?.detail || err.message}`)
    }
  }

  return (
    <div style={{ padding: '0.5rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, margin: 0, letterSpacing: '0.02em' }}>
          📁 Motion Datasets
        </h2>
        <span style={{ fontSize: 11, color: 'var(--text-secondary)', background: 'rgba(0,217,255,0.08)', padding: '2px 8px', borderRadius: 8, border: '1px solid rgba(0,217,255,0.15)' }}>
          {sessions.length} session{sessions.length !== 1 ? 's' : ''}
        </span>
      </div>

      <div style={{
        display: 'flex', flexDirection: 'column', gap: '12px',
        maxHeight: '680px', overflowY: 'auto', paddingRight: '4px'
      }} id="dataset-list">
        {loading && sessions.length === 0 ? (
          <div style={{ padding: '2rem', color: 'var(--text-secondary)', fontSize: 13, textAlign: 'center' }}>
            Loading sessions…
          </div>
        ) : sessions.length === 0 ? (
          <div style={{ padding: '2rem', color: 'var(--text-secondary)', fontSize: 13, textAlign: 'center' }}>
            No motion sessions yet.
          </div>
        ) : (
          sessions.map(s => (
            <SessionCard
              key={s.session_id}
              session={s}
              isSelected={selectedSession?.session_id === s.session_id}
              onLabel={handleLabel}
              onExport={handleExport}
              onDelete={handleDelete}
              onSelect={selectSession}
            />
          ))
        )}
      </div>
    </div>
  )
}

// ─── Session Card ────────────────────────────────────────────────────────── //
function SessionCard({ session: s, isSelected, onLabel, onExport, onDelete, onSelect }) {
  const [label, setLabel]     = useState(s.action_label)
  const [editing, setEditing] = useState(false)
  const [showExport, setShowExport] = useState(false)
  const [exporting, setExporting]   = useState(null) // id of format being downloaded

  const saveLabel = async () => {
    setEditing(false)
    await onLabel(s.session_id, label)
  }

  const handleExportClick = async (fmt, ext) => {
    setExporting(fmt)
    await onExport(s.session_id, fmt, ext)
    setTimeout(() => setExporting(null), 800)
  }

  return (
    <div
      style={{
        background: isSelected ? 'var(--bg-secondary)' : 'var(--bg-tertiary)',
        border: isSelected ? '1px solid var(--accent)' : '1px solid var(--border)',
        borderRadius: '10px',
        overflow: 'hidden',
        cursor: 'pointer',
        boxShadow: isSelected ? '0 0 16px rgba(0, 217, 255, 0.12)' : 'none',
        transition: 'all 0.2s ease',
      }}
      onClick={() => onSelect(s.session_id)}
    >
      {/* Thumbnail */}
      <div style={{ height: 100, background: '#070a13', overflow: 'hidden', position: 'relative' }}>
        {s.thumbnail_path
          ? <img
              src={`/thumbnails/${s.session_id}.jpg`}
              style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              onError={e => { e.target.style.display = 'none'; e.target.nextSibling.style.display = 'flex' }}
            />
          : null
        }
        <div style={{
          display: s.thumbnail_path ? 'none' : 'flex',
          alignItems: 'center', justifyContent: 'center',
          height: '100%', color: 'var(--text-secondary)', fontSize: 11
        }}>
          No preview
        </div>
        <div style={{
          position: 'absolute', top: 6, right: 6,
          background: 'rgba(0,0,0,0.65)', color: '#fff',
          fontSize: 10, padding: '2px 6px', borderRadius: 4,
          border: '1px solid rgba(255,255,255,0.1)'
        }}>
          {s.source_type || s.source}
        </div>
      </div>

      {/* Body */}
      <div style={{ padding: '8px 10px' }} onClick={e => e.stopPropagation()}>
        {/* Name */}
        <div style={{
          fontSize: 12, fontWeight: 600, marginBottom: 3,
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          color: isSelected ? 'var(--accent)' : 'var(--text-primary)'
        }}>
          {s.name}
        </div>

        {/* Stats */}
        <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginBottom: 6 }}>
          🎬 {s.frame_count} frames &nbsp;·&nbsp; ⏱ {s.duration_sec?.toFixed(1)}s &nbsp;·&nbsp; {s.fps} fps
        </div>

        {/* Label editor */}
        {editing ? (
          <select
            value={label} autoFocus
            onChange={e => setLabel(e.target.value)}
            onBlur={saveLabel}
            onClick={e => e.stopPropagation()}
            style={{
              fontSize: 11, width: '100%', marginBottom: 6,
              background: 'var(--bg-primary)', color: 'var(--text-primary)',
              border: '1px solid var(--border)', borderRadius: '4px', padding: '2px'
            }}
          >
            {LABELS.map(l => <option key={l} value={l}>{l}</option>)}
          </select>
        ) : (
          <div
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 4,
              background: 'rgba(0,217,255,0.08)', color: 'var(--accent)',
              fontSize: 10, padding: '2px 8px', borderRadius: 10,
              marginBottom: 8, cursor: 'pointer',
              border: '1px solid rgba(0,217,255,0.18)'
            }}
            onClick={e => { e.stopPropagation(); setEditing(true) }}
          >
            🏷 {s.action_label}
            <span style={{ fontSize: 9, opacity: 0.6 }}>✎</span>
          </div>
        )}

        {/* Action bar */}
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          {/* Export toggle */}
          <button
            id={`export-btn-${s.session_id.slice(0, 8)}`}
            style={{
              flex: 1, fontSize: 10, padding: '5px 0', cursor: 'pointer',
              background: showExport ? 'rgba(0,217,255,0.15)' : 'transparent',
              border: `1px solid ${showExport ? 'var(--accent)' : 'var(--border)'}`,
              color: showExport ? 'var(--accent)' : 'var(--text-secondary)',
              borderRadius: 5, transition: 'all 0.15s ease',
            }}
            className="btn btn-secondary"
            onClick={e => { e.stopPropagation(); setShowExport(p => !p) }}
          >
            {showExport ? '▲ Hide Export' : '⬇ Export'}
          </button>

          {/* Delete */}
          <button
            style={{ fontSize: 12, padding: '5px 8px', color: 'var(--danger)', cursor: 'pointer' }}
            className="btn btn-secondary"
            onClick={e => { e.stopPropagation(); onDelete(s.session_id) }}
          >
            🗑
          </button>
        </div>

        {/* ── Export Panel ── */}
        {showExport && (
          <ExportPanel
            sessionId={s.session_id}
            exporting={exporting}
            onExport={handleExportClick}
          />
        )}
      </div>
    </div>
  )
}

// ─── Export Panel ─────────────────────────────────────────────────────────── //
function ExportPanel({ sessionId, exporting, onExport }) {
  const categories = [...new Set(EXPORT_FORMATS.map(f => f.cat))]

  return (
    <div
      id={`export-panel-${sessionId.slice(0,8)}`}
      style={{
        marginTop: 10,
        padding: '10px 8px',
        background: 'rgba(0,0,0,0.25)',
        borderRadius: 8,
        border: '1px solid rgba(255,255,255,0.06)',
        animation: 'fadeIn 0.15s ease',
      }}
    >
      <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginBottom: 8, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
        ↓ Download Format
      </div>

      {categories.map(cat => (
        <div key={cat} style={{ marginBottom: 6 }}>
          {/* Category label */}
          <div style={{
            fontSize: 9, color: CAT_BORDER[cat], fontWeight: 700,
            letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 4,
            paddingLeft: 2,
          }}>
            {cat}
          </div>

          {/* Format buttons */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
            {EXPORT_FORMATS.filter(f => f.cat === cat).map(fmt => {
              const isLoading = exporting === fmt.id
              return (
                <button
                  key={fmt.id}
                  id={`export-${fmt.id}-${sessionId.slice(0,8)}`}
                  title={fmt.tip}
                  onClick={e => { e.stopPropagation(); onExport(fmt.id, fmt.ext) }}
                  disabled={isLoading}
                  style={{
                    fontSize: 10,
                    padding: '4px 8px',
                    cursor: isLoading ? 'wait' : 'pointer',
                    background: CAT_COLORS[cat],
                    border: `1px solid ${CAT_BORDER[cat]}`,
                    borderRadius: 5,
                    color: isLoading ? 'rgba(255,255,255,0.4)' : '#fff',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4,
                    transition: 'all 0.12s ease',
                    opacity: isLoading ? 0.7 : 1,
                    boxShadow: isLoading ? `0 0 8px ${CAT_BORDER[cat]}55` : 'none',
                    fontFamily: 'inherit',
                  }}
                  onMouseEnter={e => {
                    if (!isLoading) e.currentTarget.style.background = CAT_COLORS[cat].replace('0.1', '0.3')
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.background = CAT_COLORS[cat]
                  }}
                >
                  <span style={{ fontSize: 11 }}>{isLoading ? '⏳' : fmt.icon}</span>
                  <span>{fmt.label}</span>
                  <span style={{ opacity: 0.5, fontSize: 9 }}>{fmt.ext}</span>
                </button>
              )
            })}
          </div>
        </div>
      ))}

      <div style={{
        fontSize: 9, color: 'rgba(255,255,255,0.25)', marginTop: 8, lineHeight: 1.5,
        borderTop: '1px solid rgba(255,255,255,0.04)', paddingTop: 6
      }}>
        All formats contain identical kinematic data from a unified source.<br/>
        Hover a button to see compatible software.
      </div>
    </div>
  )
}
