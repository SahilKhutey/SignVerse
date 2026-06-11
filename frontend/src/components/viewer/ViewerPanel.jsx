export default function ViewerPanel({ frame, sessionId }) {
  if (!frame) {
    return (
      <div style={{
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        padding: 16,
        color: 'var(--text-secondary)',
        fontSize: 13,
        textAlign: 'center',
      }}>
        Select a session and click play to load active frames
      </div>
    )
  }

  const metric = frame.metric_frame || {}
  const objects = frame.objects || []

  return (
    <div style={{
      background: 'var(--bg-secondary)',
      border: '1px solid var(--border)',
      borderRadius: 12,
      padding: 16,
      display: 'flex',
      flexDirection: 'column',
      gap: 16,
    }}>
      <div>
        <h4 style={{ fontSize: 12, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 1 }}>
          Frame Metadata
        </h4>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
          <PanelRow label="Index" value={frame.frame_idx} />
          <PanelRow label="Timestamp" value={`${frame.timestamp_ms} ms`} />
          <PanelRow label="Confidence" value={`${((frame.confidence || 0) * 100).toFixed(0)}%`} />
        </div>
      </div>

      {metric && Object.keys(metric).length > 0 && (
        <div>
          <h4 style={{ fontSize: 12, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 1 }}>
            📐 Metric Estimation
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
            <PanelRow label="Person Height" value={metric.height_m ? `${metric.height_m.toFixed(2)} m` : '—'} />
            <PanelRow label="Arm Reach" value={metric.arm_reach_m ? `${metric.arm_reach_m.toFixed(2)} m` : '—'} />
            <PanelRow label="Shoulder Width" value={metric.shoulder_width_m ? `${metric.shoulder_width_m.toFixed(2)} m` : '—'} />
          </div>
        </div>
      )}

      <div>
        <h4 style={{ fontSize: 12, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 1 }}>
          📦 Tracked Objects
        </h4>
        {objects.length === 0 ? (
          <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 8 }}>
            No object tracked in this frame
          </p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
            {objects.map((obj, i) => (
              <div 
                key={i} 
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  background: 'var(--bg-tertiary)',
                  padding: '6px 10px',
                  borderRadius: 6,
                  fontSize: 12,
                }}
              >
                <span style={{ color: 'var(--accent)', fontWeight: 600 }}>{obj.class}</span>
                <span style={{ color: 'var(--text-secondary)' }}>
                  {Math.round((obj.confidence || 0) * 100)}%
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {frame.kinematics && (
        <div>
          <h4 style={{ fontSize: 12, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 1 }}>
            🤖 Kinematics / Joints
          </h4>
          <div style={{
            marginTop: 8,
            maxHeight: 200,
            overflowY: 'auto',
            border: '1px solid var(--border)',
            borderRadius: 6,
            background: 'var(--bg-tertiary)',
          }}>
            {Object.entries(frame.kinematics).map(([joint, values]) => {
              const formattedVal = Array.isArray(values) 
                ? values.map(v => typeof v === 'number' ? v.toFixed(3) : v).join(', ')
                : typeof values === 'number' ? values.toFixed(3) : JSON.stringify(values)
              return (
                <div 
                  key={joint}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    padding: '4px 8px',
                    fontSize: 11,
                    borderBottom: '1px solid var(--border)',
                    fontFamily: 'monospace',
                  }}
                >
                  <span style={{ color: 'var(--text-secondary)' }}>{joint}</span>
                  <span style={{ color: 'var(--text-primary)', textAlign: 'right', maxWidth: '65%' }}>
                    {formattedVal}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

function PanelRow({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
      <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
      <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{value}</span>
    </div>
  )
}
export { ViewerPanel }
