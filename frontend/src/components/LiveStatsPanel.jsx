import { useEffect, useState } from 'react'

const INTENT_COLORS = {
  IDLE: '#6b7280',
  WALK: '#10b981',
  GESTURE: '#f59e0b',
  WAVE: '#f59e0b',
  DRINK: '#3b82f6',
  EAT: '#3b82f6',
  TYPING: '#7c3aed',
  PHONE_CALL: '#ec4899',
  READ: '#06b6d4',
  UNKNOWN: '#6b7280',
}

const EXPRESSION_EMOJI = {
  NEUTRAL: '😐',
  HAPPY: '😊',
  SAD: '😢',
  ANGRY: '😠',
  SURPRISED: '😮',
  FEARFUL: '😨',
  DISGUSTED: '🤢',
  CONTEMPT: '😤',
}

const POSTURE_EMOJI = {
  standing: '🧍',
  sitting: '🪑',
  crouching: '🧎',
  unknown: '❓',
}

export default function LiveStatsPanel({ frame, serverFps, subscriberCount }) {
  if (!frame) {
    return (
      <div style={{
        background: '#131836',
        borderRadius: 8,
        padding: 16,
        color: '#9ca3c4',
        textAlign: 'center',
      }}>
        <div style={{ fontSize: 32, marginBottom: 8 }}>📡</div>
        <div>Waiting for live data...</div>
      </div>
    )
  }

  const intentColor = INTENT_COLORS[frame.primary_intent] || '#6b7280'
  const exprEmoji = EXPRESSION_EMOJI[frame.expression] || '😐'
  const postureEmoji = POSTURE_EMOJI[frame.person_posture] || '❓'

  return (
    <div style={{
      background: '#131836',
      borderRadius: 8,
      padding: 16,
      display: 'flex',
      flexDirection: 'column',
      gap: 12,
      border: '1px solid #2a3158',
    }}>
      {/* Top metrics row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 11, color: '#9ca3c4', textTransform: 'uppercase', letterSpacing: 1 }}>
          Live Perception
        </span>
        <div style={{ display: 'flex', gap: 12, fontSize: 11, color: '#9ca3c4' }}>
          <span>📡 {serverFps} FPS</span>
          <span>👥 {subscriberCount} client{subscriberCount !== 1 ? 's' : ''}</span>
        </div>
      </div>

      {/* Primary intent - large display */}
      <div style={{
        background: `linear-gradient(135deg, ${intentColor}22 0%, ${intentColor}11 100%)`,
        border: `1px solid ${intentColor}66`,
        borderRadius: 8,
        padding: 12,
        textAlign: 'center',
      }}>
        <div style={{ fontSize: 11, color: '#9ca3c4', marginBottom: 4 }}>
          WORK INTENT
        </div>
        <div style={{ fontSize: 24, fontWeight: 700, color: intentColor }}>
          {frame.primary_intent}
        </div>
        <div style={{ fontSize: 11, color: '#9ca3c4', marginTop: 4 }}>
          {(frame.intent_confidence * 100).toFixed(0)}% confidence
        </div>
      </div>

      {/* Action + Expression + Posture row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
        <StatBox
          label="Action"
          value={frame.primary_action}
          color="#10b981"
          icon="🎬"
        />
        <StatBox
          label="Expression"
          value={`${exprEmoji} ${frame.expression}`}
          color="#f59e0b"
          icon="😊"
        />
        <StatBox
          label="Posture"
          value={`${postureEmoji} ${frame.person_posture}`}
          color="#7c3aed"
          icon="🧍"
        />
      </div>

      {/* Hand gestures */}
      <div>
        <div style={{ fontSize: 11, color: '#9ca3c4', marginBottom: 6 }}>
          ✋ Hand Gestures
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <GesturePill
            hand="L"
            gesture={frame.hand_gestures?.left_hand || '—'}
            color="#10b981"
          />
          <GesturePill
            hand="R"
            gesture={frame.hand_gestures?.right_hand || '—'}
            color="#f59e0b"
          />
        </div>
        {frame.hand_gestures?.bimanual_pattern && (
          <div style={{
            marginTop: 6,
            fontSize: 11,
            color: '#00d9ff',
            background: 'rgba(0, 217, 255, 0.1)',
            padding: '4px 8px',
            borderRadius: 4,
            textAlign: 'center',
          }}>
            🤝 {frame.hand_gestures.bimanual_pattern}
          </div>
        )}
      </div>

      {/* Attention + Objects */}
      <div>
        <div style={{ fontSize: 11, color: '#9ca3c4', marginBottom: 6 }}>
          👀 Attention + Objects
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
            <span style={{ color: '#9ca3c4' }}>Looking at:</span>
            <span style={{ color: '#00d9ff', fontWeight: 600 }}>
              {frame.attention_target}
            </span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
            <span style={{ color: '#9ca3c4' }}>Objects in scene:</span>
            <span style={{ color: '#e4e7f1' }}>
              {frame.objects?.length || 0}
            </span>
          </div>
          {frame.interaction_graph?.primary_focus && (
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
              <span style={{ color: '#9ca3c4' }}>Primary focus:</span>
              <span style={{ color: '#7c3aed', fontWeight: 600 }}>
                {frame.interaction_graph.primary_focus.object_class}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Quality metrics */}
      <div style={{
        borderTop: '1px solid #2a3158',
        paddingTop: 8,
        display: 'flex',
        justifyContent: 'space-between',
        fontSize: 10,
        color: '#9ca3c4',
      }}>
        <span>Confidence: {(frame.pose_confidence * 100).toFixed(0)}%</span>
        <span>Process: {frame.processing_time_ms}ms</span>
        <span>Frame: {frame.frame_id}</span>
      </div>
    </div>
  )
}

function StatBox({ label, value, color, icon }) {
  return (
    <div style={{
      background: '#1c2348',
      borderRadius: 6,
      padding: 8,
      textAlign: 'center',
    }}>
      <div style={{ fontSize: 10, color: '#9ca3c4' }}>{icon} {label}</div>
      <div style={{ fontSize: 13, color, fontWeight: 600, marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {value}
      </div>
    </div>
  )
}

function GesturePill({ hand, gesture, color }) {
  return (
    <div style={{
      flex: 1,
      background: '#1c2348',
      border: `1px solid ${color}44`,
      borderRadius: 16,
      padding: '4px 10px',
      display: 'flex',
      alignItems: 'center',
      gap: 6,
    }}>
      <span style={{
        background: color,
        color: 'white',
        width: 18,
        height: 18,
        borderRadius: '50%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: 10,
        fontWeight: 700,
      }}>
        {hand}
      </span>
      <span style={{ fontSize: 12, color: '#e4e7f1', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{gesture}</span>
    </div>
  )
}
