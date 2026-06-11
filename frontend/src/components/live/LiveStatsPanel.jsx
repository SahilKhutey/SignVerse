import { Badge } from '../shared/Badge'

const INTENT_COLORS = {
  IDLE: '#6b7280', WALK: '#10b981', GESTURE: '#f59e0b',
  WAVE: '#f59e0b', DRINK: '#3b82f6', EAT: '#3b82f6',
  TYPING: '#7c3aed', PHONE_CALL: '#ec4899', READ: '#06b6d4',
}

const EXPRESSIONS = {
  NEUTRAL: '😐', HAPPY: '😊', SAD: '😢', ANGRY: '😠',
  SURPRISED: '😮', FEARFUL: '😨', DISGUSTED: '🤢',
}

const POSTURES = {
  standing: '🧍', sitting: '🪑', crouching: '🧎',
}

export default function LiveStatsPanel({ frame, serverFps, subscriberCount, liveStats }) {
  if (!frame) {
    return (
      <div style={{
        background: 'var(--bg-secondary)',
        borderRadius: 8,
        padding: 16,
        textAlign: 'center',
        color: 'var(--text-secondary)',
        fontSize: 13,
      }}>
        Waiting for live data...
      </div>
    )
  }
  
  const intentColor = INTENT_COLORS[frame.primary_intent] || '#6b7280'
  const exprEmoji = EXPRESSIONS[frame.expression] || '😐'
  const postureEmoji = POSTURES[frame.person_posture] || '❓'
  const elapsedS = liveStats?.startedAt ? Math.floor((Date.now() - liveStats.startedAt) / 1000) : 0
  
  return (
    <div style={{
      background: 'var(--bg-secondary)',
      borderRadius: 8,
      padding: 16,
      display: 'flex',
      flexDirection: 'column',
      gap: 12,
      border: '1px solid var(--border)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 1 }}>
          Live Perception
        </span>
        <div style={{ display: 'flex', gap: 10, fontSize: 10, color: 'var(--text-secondary)' }}>
          <span>📡 {serverFps} FPS</span>
          <span>👥 {subscriberCount}</span>
          <span>⏱ {elapsedS}s</span>
        </div>
      </div>
      
      {/* Primary intent */}
      <div style={{
        background: `linear-gradient(135deg, ${intentColor}22, ${intentColor}11)`,
        border: `1px solid ${intentColor}66`,
        borderRadius: 8,
        padding: 12,
        textAlign: 'center',
      }}>
        <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>WORK INTENT</div>
        <div style={{ fontSize: 22, fontWeight: 700, color: intentColor, margin: '4px 0' }}>
          {frame.primary_intent}
        </div>
        <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
          {(frame.intent_confidence * 100).toFixed(0)}% confidence
        </div>
      </div>
      
      {/* Action / Expression / Posture */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6 }}>
        <StatBox label="Action" value={frame.primary_action} color="#10b981" />
        <StatBox label="Expression" value={`${exprEmoji} ${frame.expression}`} color="#f59e0b" />
        <StatBox label="Posture" value={`${postureEmoji} ${frame.person_posture}`} color="#7c3aed" />
      </div>
      
      {/* Hands */}
      <div>
        <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginBottom: 6 }}>✋ HANDS</div>
        <div style={{ display: 'flex', gap: 6 }}>
          <GesturePill hand="L" gesture={frame.hand_gestures?.left_hand || '—'} color="#10b981" />
          <GesturePill hand="R" gesture={frame.hand_gestures?.right_hand || '—'} color="#f59e0b" />
        </div>
      </div>
      
      {/* Objects */}
      <div>
        <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginBottom: 4 }}>👀 ATTENTION</div>
        <div style={{ fontSize: 12, color: 'var(--text-primary)' }}>
          Looking at: <span style={{ color: 'var(--accent)', fontWeight: 600 }}>{frame.attention_target || 'None'}</span>
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
          Objects: {frame.objects?.length || 0} detected
        </div>
      </div>
      
      {/* Quality */}
      <div style={{
        borderTop: '1px solid var(--border)',
        paddingTop: 8,
        display: 'flex',
        justifyContent: 'space-between',
        fontSize: 10,
        color: 'var(--text-secondary)',
      }}>
        <span>Conf: {(frame.pose_confidence * 100).toFixed(0)}%</span>
        <span>Proc: {frame.processing_time_ms}ms</span>
        <span>Frames: {liveStats?.framesProcessed || 0}</span>
      </div>
    </div>
  )
}

function StatBox({ label, value, color }) {
  return (
    <div style={{
      background: 'var(--bg-tertiary)',
      borderRadius: 6,
      padding: 8,
      textAlign: 'center',
    }}>
      <div style={{ fontSize: 9, color: 'var(--text-secondary)' }}>{label}</div>
      <div style={{ fontSize: 11, color, fontWeight: 600, marginTop: 2 }}>{value}</div>
    </div>
  )
}

function GesturePill({ hand, gesture, color }) {
  return (
    <div style={{
      flex: 1,
      background: 'var(--bg-tertiary)',
      border: `1px solid ${color}44`,
      borderRadius: 14,
      padding: '4px 8px',
      display: 'flex',
      alignItems: 'center',
      gap: 5,
    }}>
      <span style={{
        background: color, color: 'white',
        width: 16, height: 16, borderRadius: '50%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 9, fontWeight: 700,
      }}>{hand}</span>
      <span style={{ fontSize: 10, color: 'var(--text-primary)' }}>{gesture}</span>
    </div>
  )
}
export { LiveStatsPanel }
