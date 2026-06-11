import Button from '../shared/Button'

export default function PlaybackControls({
  current,
  total,
  playing,
  onPlayToggle,
  onScrub,
  fps,
  onFpsChange
}) {
  return (
    <div style={{
      background: 'var(--bg-tertiary)',
      borderTop: '1px solid var(--border)',
      padding: '12px 16px',
      display: 'flex',
      flexDirection: 'column',
      gap: 10,
    }}>
      {/* Timeline scrubbing track */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span style={{ fontSize: 11, color: 'var(--text-secondary)', fontFamily: 'monospace', width: 30 }}>
          {current}
        </span>
        <div style={{ flex: 1, position: 'relative' }}>
          <input
            type="range"
            min="0"
            max={total - 1}
            value={current}
            onChange={(e) => onScrub(Number(e.target.value))}
            style={{
              width: '100%',
              accentColor: 'var(--accent)',
              cursor: 'pointer',
            }}
          />
        </div>
        <span style={{ fontSize: 11, color: 'var(--text-secondary)', fontFamily: 'monospace', width: 30, ...{textAlign: 'right'} }}>
          {total - 1}
        </span>
      </div>

      {/* Control Buttons & FPS */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => onScrub(Math.max(0, current - 1))}
            disabled={playing}
          >
            ⏮ Step Back
          </Button>
          <Button
            size="sm"
            onClick={onPlayToggle}
            style={{ minWidth: 80 }}
          >
            {playing ? '⏸ Pause' : '▶ Play'}
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => onScrub(Math.min(total - 1, current + 1))}
            disabled={playing}
          >
            Step Fwd ⏭
          </Button>
        </div>

        {/* FPS selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
          <span style={{ color: 'var(--text-secondary)' }}>Speed:</span>
          <select
            value={fps}
            onChange={(e) => onFpsChange(Number(e.target.value))}
            style={{
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border)',
              color: 'var(--text-primary)',
              borderRadius: 4,
              padding: '2px 8px',
              cursor: 'pointer',
            }}
          >
            <option value="15">15 FPS</option>
            <option value="30">30 FPS</option>
            <option value="60">60 FPS</option>
          </select>
        </div>
      </div>
    </div>
  )
}
export { PlaybackControls }
