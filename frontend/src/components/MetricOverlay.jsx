import { useState, useEffect } from 'react'

const CANONICAL_POSE_JOINTS = [
  { id: 0,  label: "Nose / Crown" },
  { id: 11, label: "Left Shoulder" },
  { id: 12, label: "Right Shoulder" },
  { id: 13, label: "Left Elbow" },
  { id: 14, label: "Right Elbow" },
  { id: 15, label: "Left Wrist" },
  { id: 16, label: "Right Wrist" },
  { id: 23, label: "Left Hip" },
  { id: 24, label: "Right Hip" },
  { id: 25, label: "Left Knee" },
  { id: 26, label: "Right Knee" },
  { id: 27, label: "Left Ankle" },
  { id: 28, label: "Right Ankle" },
]

export default function MetricOverlay({ metricFrame }) {
  const [jointA, setJointA] = useState(11) // Default Left Shoulder
  const [jointB, setJointB] = useState(12) // Default Right Shoulder
  const [rulerDistance, setRulerDistance] = useState(null)

  useEffect(() => {
    if (!metricFrame || !metricFrame.pose_33_metric || metricFrame.pose_33_metric.length === 0) {
      setRulerDistance(null)
      return
    }

    const pose = metricFrame.pose_33_metric
    if (jointA < pose.length && jointB < pose.length) {
      const ptA = pose[jointA]
      const ptB = pose[jointB]
      if (ptA && ptB) {
        const dx = ptA[0] - ptB[0]
        const dy = ptA[1] - ptB[1]
        const dz = ptA[2] - ptB[2]
        const distance = Math.sqrt(dx * dx + dy * dy + dz * dz)
        setRulerDistance(distance)
      } else {
        setRulerDistance(null)
      }
    } else {
      setRulerDistance(null)
    }
  }, [metricFrame, jointA, jointB])

  if (!metricFrame) return null

  // Metric info fields
  const height = metricFrame.person_height_m
  const lArm = metricFrame.left_arm_length_m
  const rArm = metricFrame.right_arm_length_m
  const shoulder = metricFrame.shoulder_width_m
  const scale = metricFrame.scale_factor
  const confidence = metricFrame.depth_confidence || 1.0

  // Determine badge color
  let confColor = '#00ff80'
  let confText = 'HIGH'
  if (confidence < 0.4) {
    confColor = '#ff3b30'
    confText = 'LOW'
  } else if (confidence < 0.7) {
    confColor = '#ffcc00'
    confText = 'MEDIUM'
  }

  return (
    <div style={{
      position: 'absolute',
      top: '12px',
      left: '12px',
      width: '280px',
      zIndex: 10,
      fontFamily: 'Inter, system-ui, sans-serif',
      display: 'flex',
      flexDirection: 'column',
      gap: '8px',
      pointerEvents: 'auto',
    }}>
      {/* ── Biomechanical measurements overlay ── */}
      <div style={{
        background: 'rgba(10, 15, 30, 0.75)',
        backdropFilter: 'blur(10px)',
        border: '1px solid rgba(0, 217, 255, 0.25)',
        borderRadius: '8px',
        padding: '12px',
        color: '#ffffff',
        boxShadow: '0 8px 32px 0 rgba(0, 0, 0, 0.5)',
      }}>
        <div style={{
          fontSize: '11px',
          fontWeight: 700,
          color: 'var(--accent)',
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          marginBottom: '8px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <span>📐 Metric Analysis</span>
          <span style={{
            fontSize: '9px',
            background: `${confColor}22`,
            color: confColor,
            border: `1px solid ${confColor}44`,
            padding: '2px 6px',
            borderRadius: '4px',
          }} title={`Confidence Score: ${(confidence * 100).toFixed(0)}%`}>
            {confText}
          </span>
        </div>

        {/* Data list */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--text-secondary)' }}>Height:</span>
            <span style={{ fontWeight: 600 }}>{height ? `${(height * 100).toFixed(1)} cm` : 'Calculating...'}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--text-secondary)' }}>Shoulder Width:</span>
            <span style={{ fontWeight: 600 }}>{shoulder ? `${(shoulder * 100).toFixed(1)} cm` : 'Calculating...'}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--text-secondary)' }}>Left Arm Reach:</span>
            <span style={{ fontWeight: 600 }}>{lArm ? `${(lArm * 100).toFixed(1)} cm` : 'Calculating...'}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--text-secondary)' }}>Right Arm Reach:</span>
            <span style={{ fontWeight: 600 }}>{rArm ? `${(rArm * 100).toFixed(1)} cm` : 'Calculating...'}</span>
          </div>
          
          <div style={{
            borderTop: '1px solid rgba(255, 255, 255, 0.1)',
            paddingTop: '6px',
            marginTop: '4px',
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: '11px',
          }}>
            <span style={{ color: 'rgba(255, 255, 255, 0.5)' }}>Scale Factor:</span>
            <span style={{ fontFamily: 'monospace', color: 'var(--accent)' }}>{scale ? `${scale.toFixed(3)} m/u` : 'N/A'}</span>
          </div>
        </div>
      </div>

      {/* ── Ruler Tool Overlay ── */}
      <div style={{
        background: 'rgba(10, 15, 30, 0.75)',
        backdropFilter: 'blur(10px)',
        border: '1px solid rgba(244, 63, 94, 0.25)',
        borderRadius: '8px',
        padding: '12px',
        color: '#ffffff',
        boxShadow: '0 8px 32px 0 rgba(0, 0, 0, 0.5)',
      }}>
        <div style={{
          fontSize: '11px',
          fontWeight: 700,
          color: '#f43f5e',
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          marginBottom: '8px',
        }}>
          📏 Skeletal Ruler
        </div>

        {/* Dropdowns */}
        <div style={{ display: 'flex', gap: '6px', marginBottom: '10px' }}>
          <select
            value={jointA}
            onChange={e => setJointA(Number(e.target.value))}
            style={{
              flex: 1,
              background: 'rgba(255,255,255,0.06)',
              color: '#fff',
              border: '1px solid rgba(255,255,255,0.15)',
              borderRadius: '4px',
              fontSize: '11px',
              padding: '4px 2px',
              cursor: 'pointer',
            }}
          >
            {CANONICAL_POSE_JOINTS.map(j => (
              <option key={j.id} value={j.id} style={{ background: '#0a0f1e' }}>
                A: {j.label}
              </option>
            ))}
          </select>

          <select
            value={jointB}
            onChange={e => setJointB(Number(e.target.value))}
            style={{
              flex: 1,
              background: 'rgba(255,255,255,0.06)',
              color: '#fff',
              border: '1px solid rgba(255,255,255,0.15)',
              borderRadius: '4px',
              fontSize: '11px',
              padding: '4px 2px',
              cursor: 'pointer',
            }}
          >
            {CANONICAL_POSE_JOINTS.map(j => (
              <option key={j.id} value={j.id} style={{ background: '#0a0f1e' }}>
                B: {j.label}
              </option>
            ))}
          </select>
        </div>

        {/* Result display */}
        <div style={{
          background: 'rgba(244, 63, 94, 0.08)',
          border: '1px dashed rgba(244, 63, 94, 0.3)',
          borderRadius: '4px',
          padding: '8px 10px',
          textAlign: 'center',
        }}>
          <div style={{ fontSize: '10px', color: 'rgba(255,255,255,0.5)', marginBottom: '2px' }}>
            Calculated 3D Distance:
          </div>
          <div style={{
            fontSize: '16px',
            fontWeight: 700,
            color: '#f43f5e',
            fontFamily: 'monospace',
          }}>
            {rulerDistance !== null ? `${(rulerDistance * 100).toFixed(1)} cm` : '--'}
          </div>
        </div>
      </div>
    </div>
  )
}
