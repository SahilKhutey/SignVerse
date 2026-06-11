import { useEffect, useRef } from 'react'

// Skeleton connection definitions (MediaPipe topology)
const POSE_CONNECTIONS = [
  // Torso
  [11, 12], [11, 23], [12, 24], [23, 24],
  // Arms
  [11, 13], [13, 15], [12, 14], [14, 16],
  // Legs
  [23, 25], [25, 27], [24, 26], [26, 28],
  // Feet
  [27, 29], [27, 31], [28, 30], [28, 32],
  // Face
  [0, 11], [0, 12],  // nose to shoulders
]

const HAND_CONNECTIONS = [
  // Thumb
  [0, 1], [1, 2], [2, 3], [3, 4],
  // Index
  [0, 5], [5, 6], [6, 7], [7, 8],
  // Middle
  [0, 9], [9, 10], [10, 11], [11, 12],
  // Ring
  [0, 13], [13, 14], [14, 15], [15, 16],
  // Pinky
  [0, 17], [17, 18], [18, 19], [19, 20],
  // Palm
  [5, 9], [9, 13], [13, 17],
]

// Color by joint type
const COLORS = {
  pose: { line: '#00d9ff', joint: '#7c3aed', confidence: '#10b981' },
  hand_left: { line: '#10b981', joint: '#34d399' },
  hand_right: { line: '#f59e0b', joint: '#fbbf24' },
  face: { line: '#9ca3c4', joint: '#9ca3c4' },
  object: { line: '#ef4444', joint: '#ef4444' },
}

/**
 * Live skeleton overlay component.
 * Draws MediaPipe pose + hands + face + object bboxes on a canvas.
 */
export default function LiveSkeletonOverlay({
  frame,
  width = 640,
  height = 480,
  showFace = true,
  showHands = true,
  showObjects = true,
  showLabels = true,
  confidenceColorCoding = true,
}) {
  const canvasRef = useRef(null)
  const animRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')

    const draw = () => {
      // Clear
      ctx.clearRect(0, 0, width, height)

      if (!frame) {
        // Draw "waiting" state
        ctx.fillStyle = 'rgba(10, 14, 39, 0.9)'
        ctx.fillRect(0, 0, width, height)
        ctx.fillStyle = '#9ca3c4'
        ctx.font = '20px Inter, sans-serif'
        ctx.textAlign = 'center'
        ctx.fillText('Waiting for live data...', width / 2, height / 2)
        animRef.current = requestAnimationFrame(draw)
        return
      }

      // Draw background (subtle)
      ctx.fillStyle = 'rgba(10, 14, 39, 0.0)'
      ctx.fillRect(0, 0, width, height)

      // === Draw objects (YOLO bboxes) ===
      if (showObjects && frame.objects) {
        frame.objects.forEach((obj) => {
          const [x1, y1, x2, y2] = obj.bbox
          ctx.strokeStyle = COLORS.object.line
          ctx.lineWidth = 2
          ctx.strokeRect(x1, y1, x2 - x1, y2 - y1)

          // Label
          if (showLabels) {
            const label = `${obj.class} ${Math.round(obj.confidence * 100)}%`
            ctx.fillStyle = COLORS.object.line
            ctx.font = '12px Inter, sans-serif'
            const textW = ctx.measureText(label).width
            ctx.fillRect(x1, y1 - 16, textW + 8, 16)
            ctx.fillStyle = 'white'
            ctx.fillText(label, x1 + 4, y1 - 4)
          }
        })
      }

      // === Draw pose (33 joints) ===
      if (frame.pose_33 && frame.pose_33.length >= 33) {
        // Draw bones
        ctx.strokeStyle = COLORS.pose.line
        ctx.lineWidth = 3
        POSE_CONNECTIONS.forEach(([a, b]) => {
          if (a < frame.pose_33.length && b < frame.pose_33.length) {
            const pa = frame.pose_33[a]
            const pb = frame.pose_33[b]
            if (pa.v > 0.3 && pb.v > 0.3) {
              drawLineWithConfidence(ctx, pa, pb, width, height, confidenceColorCoding)
            }
          }
        })

        // Draw joints
        frame.pose_33.forEach((lm) => {
          if (lm.v > 0.3) {
            drawJointWithConfidence(ctx, lm, width, height, confidenceColorCoding)
          }
        })
      }

      // === Draw left hand (21 joints) ===
      if (showHands && frame.left_hand_21 && frame.left_hand_21.length === 21) {
        ctx.strokeStyle = COLORS.hand_left.line
        ctx.lineWidth = 2
        HAND_CONNECTIONS.forEach(([a, b]) => {
          const pa = frame.left_hand_21[a]
          const pb = frame.left_hand_21[b]
          if (pa && pb) {
            ctx.beginPath()
            ctx.moveTo(pa.x * width, pa.y * height)
            ctx.lineTo(pb.x * width, pb.y * height)
            ctx.stroke()
          }
        })
        frame.left_hand_21.forEach((lm) => {
          ctx.fillStyle = COLORS.hand_left.joint
          ctx.beginPath()
          ctx.arc(lm.x * width, lm.y * height, 3, 0, Math.PI * 2)
          ctx.fill()
        })
      }

      // === Draw right hand (21 joints) ===
      if (showHands && frame.right_hand_21 && frame.right_hand_21.length === 21) {
        ctx.strokeStyle = COLORS.hand_right.line
        ctx.lineWidth = 2
        HAND_CONNECTIONS.forEach(([a, b]) => {
          const pa = frame.right_hand_21[a]
          const pb = frame.right_hand_21[b]
          if (pa && pb) {
            ctx.beginPath()
            ctx.moveTo(pa.x * width, pa.y * height)
            ctx.lineTo(pb.x * width, pb.y * height)
            ctx.stroke()
          }
        })
        frame.right_hand_21.forEach((lm) => {
          ctx.fillStyle = COLORS.hand_right.joint
          ctx.beginPath()
          ctx.arc(lm.x * width, lm.y * height, 3, 0, Math.PI * 2)
          ctx.fill()
        })
      }

      // === Draw face mesh (478 points) ===
      if (showFace && frame.face_478 && frame.face_478.length > 0) {
        ctx.fillStyle = COLORS.face.joint
        frame.face_478.forEach((lm) => {
          ctx.globalAlpha = 0.4
          ctx.beginPath()
          ctx.arc(lm.x * width, lm.y * height, 1, 0, Math.PI * 2)
          ctx.fill()
        })
        ctx.globalAlpha = 1.0
      }

      // === Draw HUD ===
      drawHUD(ctx, frame, width, height)

      animRef.current = requestAnimationFrame(draw)
    }

    draw()

    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current)
    }
  }, [frame, width, height, showFace, showHands, showObjects, showLabels, confidenceColorCoding])

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      style={{
        display: 'block',
        width: '100%',
        height: '100%',
        objectFit: 'contain',
        background: 'transparent',
      }}
    />
  )
}

function drawLineWithConfidence(ctx, a, b, w, h, useConfidence) {
  const avgConf = (a.v + b.v) / 2
  if (useConfidence) {
    if (avgConf > 0.7) ctx.strokeStyle = '#10b981'        // green
    else if (avgConf > 0.4) ctx.strokeStyle = '#f59e0b'   // amber
    else ctx.strokeStyle = '#ef4444'                       // red
  }
  ctx.lineWidth = 2 + avgConf * 2
  ctx.beginPath()
  ctx.moveTo(a.x * w, a.y * h)
  ctx.lineTo(b.x * w, b.y * h)
  ctx.stroke()
}

function drawJointWithConfidence(ctx, lm, w, h, useConfidence) {
  let color = '#7c3aed'
  if (useConfidence) {
    if (lm.v > 0.7) color = '#10b981'
    else if (lm.v > 0.4) color = '#f59e0b'
    else color = '#ef4444'
  }
  ctx.fillStyle = color
  ctx.beginPath()
  ctx.arc(lm.x * w, lm.y * h, 4, 0, Math.PI * 2)
  ctx.fill()
  
  ctx.fillStyle = 'white'
  ctx.beginPath()
  ctx.arc(lm.x * w, lm.y * h, 1.5, 0, Math.PI * 2)
  ctx.fill()
}

function drawHUD(ctx, frame, w, h) {
  ctx.fillStyle = 'rgba(0, 0, 0, 0.6)'
  ctx.fillRect(0, 0, w, 60)
  ctx.fillStyle = '#00d9ff'
  ctx.font = 'bold 14px Inter, monospace'
  ctx.textAlign = 'left'
  ctx.fillText(`Frame: ${frame.frame_id}  |  ${frame.timestamp_ms}ms`, 10, 22)
  ctx.fillText(`Confidence: ${(frame.pose_confidence * 100).toFixed(1)}%  |  ${Math.round(frame.processing_time_ms)}ms`, 10, 42)

  ctx.textAlign = 'right'
  ctx.font = 'bold 12px Inter, sans-serif'
  ctx.fillStyle = '#7c3aed'
  ctx.fillText(`Intent: ${frame.primary_intent || frame.primary_intent || 'IDLE'}`, w - 10, 18)
  ctx.fillStyle = '#10b981'
  ctx.fillText(`Action: ${frame.primary_action || 'IDLE'}`, w - 10, 36)
  ctx.fillStyle = '#f59e0b'
  ctx.fillText(`Expression: ${frame.expression || 'NEUTRAL'}`, w - 10, 54)

  if (frame.hand_gestures) {
    ctx.textAlign = 'left'
    ctx.fillStyle = 'rgba(0, 0, 0, 0.6)'
    ctx.fillRect(0, h - 40, w, 40)
    ctx.fillStyle = '#e4e7f1'
    ctx.font = '12px Inter, monospace'
    ctx.fillText(
      `L: ${frame.hand_gestures.left_hand || '—'}  |  R: ${frame.hand_gestures.right_hand || '—'}`,
      10, h - 20
    )
    if (frame.hand_gestures.bimanual_pattern) {
      ctx.fillStyle = '#00d9ff'
      ctx.fillText(`Bimanual: ${frame.hand_gestures.bimanual_pattern}`, 200, h - 20)
    }
  }
}
