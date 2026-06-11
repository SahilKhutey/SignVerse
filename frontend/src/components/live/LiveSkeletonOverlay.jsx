import { useEffect, useRef } from 'react'

const POSE_CONNECTIONS = [
  [11, 12], [11, 13], [13, 15], [12, 14], [14, 16],
  [11, 23], [12, 24], [23, 24],
  [23, 25], [25, 27], [24, 26], [26, 28],
  [27, 31], [28, 32], [27, 29], [28, 30],
  [0, 11], [0, 12],
]

const HAND_CONNECTIONS = [
  [0, 1], [1, 2], [2, 3], [3, 4],
  [0, 5], [5, 6], [6, 7], [7, 8],
  [0, 9], [9, 10], [10, 11], [11, 12],
  [0, 13], [13, 14], [14, 15], [15, 16],
  [0, 17], [17, 18], [18, 19], [19, 20],
  [5, 9], [9, 13], [13, 17],
]

export default function LiveSkeletonOverlay({ 
  frame, width = 640, height = 480,
  showFace = true, showHands = true, showObjects = true 
}) {
  const canvasRef = useRef(null)
  const animRef = useRef(null)
  
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    
    const draw = () => {
      ctx.clearRect(0, 0, width, height)
      
      if (!frame) {
        ctx.fillStyle = '#9ca3c4'
        ctx.font = '14px sans-serif'
        ctx.textAlign = 'center'
        ctx.fillText('Waiting for live data...', width / 2, height / 2)
        animRef.current = requestAnimationFrame(draw)
        return
      }
      
      // Draw objects
      if (showObjects && frame.objects) {
        frame.objects.forEach(obj => {
          const [x1, y1, x2, y2] = obj.bbox
          ctx.strokeStyle = '#ef4444'
          ctx.lineWidth = 2
          ctx.strokeRect(x1, y1, x2 - x1, y2 - y1)
          ctx.fillStyle = '#ef4444'
          ctx.font = '11px sans-serif'
          const label = `${obj.class} ${Math.round((obj.confidence || 0) * 100)}%`
          ctx.fillText(label, x1 + 4, y1 - 4)
        })
      }
      
      // Draw pose
      if (frame.pose_33 && frame.pose_33.length >= 33) {
        ctx.strokeStyle = '#00d9ff'
        ctx.lineWidth = 3
        POSE_CONNECTIONS.forEach(([a, b]) => {
          if (a < frame.pose_33.length && b < frame.pose_33.length) {
            const pa = frame.pose_33[a]
            const pb = frame.pose_33[b]
            if (pa.v > 0.3 && pb.v > 0.3) {
              ctx.beginPath()
              ctx.moveTo(pa.x * width, pa.y * height)
              ctx.lineTo(pb.x * width, pb.y * height)
              ctx.stroke()
            }
          }
        })
        
        frame.pose_33.forEach(lm => {
          if (lm.v > 0.3) {
            ctx.fillStyle = '#7c3aed'
            ctx.beginPath()
            ctx.arc(lm.x * width, lm.y * height, 5, 0, Math.PI * 2)
            ctx.fill()
            ctx.fillStyle = 'white'
            ctx.beginPath()
            ctx.arc(lm.x * width, lm.y * height, 2, 0, Math.PI * 2)
            ctx.fill()
          }
        })
      }
      
      // Draw hands
      if (showHands) {
        if (frame.left_hand_21?.length === 21) {
          drawHand(ctx, frame.left_hand_21, '#10b981', width, height)
        }
        if (frame.right_hand_21?.length === 21) {
          drawHand(ctx, frame.right_hand_21, '#f59e0b', width, height)
        }
      }
      
      // Draw face dots
      if (showFace && frame.face_478?.length > 0) {
        ctx.fillStyle = 'rgba(156, 163, 196, 0.5)'
        frame.face_478.forEach(lm => {
          ctx.beginPath()
          ctx.arc(lm.x * width, lm.y * height, 1, 0, Math.PI * 2)
          ctx.fill()
        })
      }
      
      // HUD
      drawHUD(ctx, frame, width, height)
      
      animRef.current = requestAnimationFrame(draw)
    }
    
    draw()
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current) }
  }, [frame, width, height, showFace, showHands, showObjects])
  
  return <canvas ref={canvasRef} width={width} height={height} style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
}

function drawHand(ctx, hand, color, w, h) {
  ctx.strokeStyle = color
  ctx.lineWidth = 2
  HAND_CONNECTIONS.forEach(([a, b]) => {
    if (a < hand.length && b < hand.length) {
      ctx.beginPath()
      ctx.moveTo(hand[a].x * w, hand[a].y * h)
      ctx.lineTo(hand[b].x * w, hand[b].y * h)
      ctx.stroke()
    }
  })
  hand.forEach(lm => {
    ctx.fillStyle = color
    ctx.beginPath()
    ctx.arc(lm.x * w, lm.y * h, 3, 0, Math.PI * 2)
    ctx.fill()
  })
}

function drawHUD(ctx, frame, w, h) {
  ctx.fillStyle = 'rgba(0,0,0,0.6)'
  ctx.fillRect(0, 0, w, 55)
  ctx.fillStyle = '#00d9ff'
  ctx.font = 'bold 11px monospace'
  ctx.textAlign = 'left'
  
  const frameId = frame.frame_id !== undefined && frame.frame_id !== null ? frame.frame_id : 0
  const timestamp = frame.timestamp_ms !== undefined && frame.timestamp_ms !== null ? frame.timestamp_ms : 0
  const poseConf = frame.pose_confidence !== undefined && frame.pose_confidence !== null ? (frame.pose_confidence * 100).toFixed(0) : '0'
  const procTime = frame.processing_time_ms !== undefined && frame.processing_time_ms !== null ? frame.processing_time_ms.toFixed(0) : '0'
  const intent = frame.primary_intent || 'IDLE'
  const intentConf = frame.intent_confidence !== undefined && frame.intent_confidence !== null ? (frame.intent_confidence * 100).toFixed(0) : '0'
  const action = frame.primary_action || 'IDLE'
  
  ctx.fillText(`Frame ${frameId} | ${timestamp}ms`, 10, 20)
  ctx.fillText(`Conf: ${poseConf}% | ${procTime}ms`, 10, 40)
  
  ctx.textAlign = 'right'
  ctx.fillStyle = '#7c3aed'
  ctx.fillText(`Intent: ${intent} (${intentConf}%)`, w - 10, 20)
  ctx.fillStyle = '#10b981'
  ctx.fillText(`Action: ${action}`, w - 10, 40)
}
