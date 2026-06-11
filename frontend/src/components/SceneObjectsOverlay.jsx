import { useEffect, useRef } from 'react'

// HOI type → badge color
const HOI_COLORS = {
  APPROACHING: '#4488ff',
  NEAR:        '#ffcc00',
  TOUCHING:    '#ff8800',
  GRASPING:    '#ff4400',
  HOLDING:     '#00e676',
  LIFTING:     '#00e5ff',
  MOVING:      '#7c4dff',
  PLACING:     '#ff6d00',
  RELEASING:   '#e040fb',
  POINTING:    '#40c4ff',
  USING:       '#69f0ae',
}

// Class → emoji icon
const CLASS_ICONS = {
  cup: '☕', bottle: '🍶', 'wine glass': '🍷', bowl: '🥣',
  'cell phone': '📱', laptop: '💻', keyboard: '⌨️', mouse: '🖱️', remote: '📺',
  book: '📖', scissors: '✂️', knife: '🔪', fork: '🍴', spoon: '🥄',
  apple: '🍎', banana: '🍌', orange: '🍊', sandwich: '🥪', pizza: '🍕',
  backpack: '🎒', handbag: '👜', suitcase: '🧳', umbrella: '☂️',
  'baseball bat': '⚾', 'tennis racket': '🎾', frisbee: '🥏',
  'sports ball': '⚽', skateboard: '🛹',
  chair: '🪑', couch: '🛋️', vase: '🏺', clock: '🕐', scissors: '✂️',
  toothbrush: '🪥', 'hair drier': '💨', 'teddy bear': '🧸',
}

export default function SceneObjectsOverlay({ objects = [], interactions = [], canvasWidth = 640, canvasHeight = 480 }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // Draw each object bbox
    for (const obj of objects) {
      const [x1, y1, x2, y2] = obj.bbox || [0,0,0,0]
      const w = x2 - x1, h = y2 - y1
      if (w < 2 || h < 2) continue

      const cls   = obj.class || obj.class_name || 'object'
      const tid   = obj.track_id
      const conf  = obj.confidence || 0
      const pos3d = obj.position_3d
      const depth = obj.depth_m

      // Find active interaction for this object
      const iaction = interactions.find(
        ia => ia.object_id === tid || ia.object_track_id === tid
      )
      const itype = iaction?.interaction_type || 'NEAR'
      const color = HOI_COLORS[itype] || '#ffffff'

      // Glow on active interaction
      if (iaction) {
        ctx.shadowColor = color
        ctx.shadowBlur  = 12
      } else {
        ctx.shadowBlur = 0
      }

      // Bounding box
      ctx.strokeStyle = color
      ctx.lineWidth   = iaction ? 2.5 : 1.5
      ctx.setLineDash(iaction ? [] : [4, 4])
      ctx.strokeRect(x1, y1, w, h)
      ctx.setLineDash([])
      ctx.shadowBlur = 0

      // Label background
      const icon  = CLASS_ICONS[cls] || '📦'
      const label = `${icon} ${cls}`
      ctx.font = 'bold 11px Inter, sans-serif'
      const textW = ctx.measureText(label).width + 8

      ctx.fillStyle = `${color}dd`
      ctx.fillRect(x1, y1 - 18, textW, 18)

      ctx.fillStyle = '#000'
      ctx.fillText(label, x1 + 4, y1 - 4)

      // Depth + interaction badge (top-right)
      if (depth || iaction) {
        const badge = [
          depth ? `${depth.toFixed(1)}m` : '',
          iaction ? itype.toLowerCase() : '',
        ].filter(Boolean).join(' · ')

        ctx.font = '9px Inter, monospace'
        const bw = ctx.measureText(badge).width + 8
        ctx.fillStyle = 'rgba(0,0,0,0.7)'
        ctx.fillRect(x2 - bw, y1, bw, 16)
        ctx.fillStyle = color
        ctx.fillText(badge, x2 - bw + 4, y1 + 11)
      }

      // Track ID + confidence (bottom-left)
      const meta = `#${tid}  ${(conf*100).toFixed(0)}%`
      ctx.font = '9px monospace'
      const mw = ctx.measureText(meta).width + 6
      ctx.fillStyle = 'rgba(0,0,0,0.55)'
      ctx.fillRect(x1, y2 - 14, mw, 14)
      ctx.fillStyle = 'rgba(255,255,255,0.6)'
      ctx.fillText(meta, x1 + 3, y2 - 3)

      // 3D position indicator (if available)
      if (pos3d) {
        const posLabel = `[${pos3d.map(v=>v.toFixed(2)).join(', ')}]`
        ctx.font = '8px monospace'
        ctx.fillStyle = 'rgba(0,0,0,0.5)'
        ctx.fillRect(x1, y2, ctx.measureText(posLabel).width + 6, 12)
        ctx.fillStyle = 'rgba(0,217,255,0.7)'
        ctx.fillText(posLabel, x1 + 3, y2 + 9)
      }
    }

    // Draw interaction connection lines (hand → object)
    for (const ia of interactions) {
      if (!ia.contact_point || !ia.contact_point[0]) continue
      const color = HOI_COLORS[ia.interaction_type] || '#ffffff'
      const [cx, cy] = [ia.contact_point[0], ia.contact_point[1]]

      ctx.beginPath()
      ctx.arc(cx, cy, 5, 0, Math.PI * 2)
      ctx.strokeStyle = color
      ctx.lineWidth = 2
      ctx.stroke()

      ctx.beginPath()
      ctx.arc(cx, cy, 2, 0, Math.PI * 2)
      ctx.fillStyle = color
      ctx.fill()
    }
  }, [objects, interactions, canvasWidth, canvasHeight])

  return (
    <canvas
      ref={canvasRef}
      width={canvasWidth}
      height={canvasHeight}
      style={{
        position: 'absolute',
        top: 0, left: 0,
        width: '100%', height: '100%',
        pointerEvents: 'none',
      }}
    />
  )
}
