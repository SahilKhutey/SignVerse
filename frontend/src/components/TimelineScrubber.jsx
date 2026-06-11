import React from 'react'

export default function TimelineScrubber({ frame, total, onChange, playing, onTogglePlay }) {
  const handleScrub = (e) => {
    onChange(parseInt(e.target.value, 10))
  }

  const stepBack = () => {
    onChange((prev) => Math.max(0, prev - 1))
  }

  const stepForward = () => {
    onChange((prev) => Math.min(total - 1, prev + 1))
  }

  return (
    <div style={{
      marginTop: '1rem',
      background: 'var(--bg-secondary)',
      border: '1px solid var(--border)',
      borderRadius: '8px',
      padding: '0.75rem 1rem',
    }}>
      {/* Playback Controls & Slider in one row or flex column */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <button
          onClick={onTogglePlay}
          className="btn"
          style={{
            width: '40px',
            height: '40px',
            padding: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '1.2rem',
            borderRadius: '50%',
            background: 'linear-gradient(135deg, var(--accent), var(--accent-2))',
            color: 'white',
            border: 'none',
            cursor: 'pointer',
            flexShrink: 0
          }}
        >
          {playing ? '⏸' : '▶'}
        </button>

        <button
          onClick={stepBack}
          disabled={frame <= 0}
          className="btn btn-secondary"
          style={{ width: 'auto', padding: '6px 12px', fontSize: '0.8rem' }}
        >
          ⏮ Step
        </button>

        <input
          type="range"
          min={0}
          max={Math.max(0, total - 1)}
          value={frame}
          onChange={handleScrub}
          style={{
            flex: 1,
            height: '6px',
            borderRadius: '3px',
            background: 'var(--bg-tertiary)',
            outline: 'none',
            cursor: 'pointer',
            accentColor: 'var(--accent)',
          }}
        />

        <button
          onClick={stepForward}
          disabled={frame >= total - 1}
          className="btn btn-secondary"
          style={{ width: 'auto', padding: '6px 12px', fontSize: '0.8rem' }}
        >
          Step ⏭
        </button>
      </div>

      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        marginTop: '8px',
        fontSize: '0.75rem',
        color: 'var(--text-secondary)'
      }}>
        <span>Frame {frame} of {total}</span>
        <span>Duration: {((total) / 30.0).toFixed(1)}s (30 FPS)</span>
      </div>
    </div>
  )
}
