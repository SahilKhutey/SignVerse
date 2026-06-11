import { useState, useEffect } from 'react'
import axios from 'axios'

const API = '/api'

export default function ActionLabeler({ sessionId, currentLabel, onUpdate }) {
  const [label, setLabel] = useState(currentLabel || 'unlabeled')
  const [notes, setNotes] = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState(null)

  useEffect(() => {
    setLabel(currentLabel || 'unlabeled')
    setMessage(null)
    
    // Load current session notes if available
    if (sessionId) {
      axios.get(`${API}/dataset/${sessionId}`)
        .then(({ data }) => setNotes(data.notes || ''))
        .catch(() => {})
    }
  }, [sessionId, currentLabel])

  const save = async (e) => {
    e.preventDefault()
    setLoading(true)
    setMessage(null)
    try {
      await axios.post(`${API}/dataset/${sessionId}/label`, {
        action_label: label,
        notes: notes,
      })
      setMessage('✅ Label saved successfully!')
      onUpdate?.(label)
    } catch (err) {
      console.error(err)
      setMessage('❌ Failed to save label')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      marginTop: '1rem',
      background: 'var(--bg-secondary)',
      border: '1px solid var(--border)',
      borderRadius: '8px',
      padding: '1rem',
    }}>
      <h3 style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
        🏷️ Session Label metadata
      </h3>
      <form onSubmit={save} style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <div style={{ display: 'flex', gap: '8px' }}>
          <select
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            style={{
              flex: 1,
              background: 'var(--bg-tertiary)',
              border: '1px solid var(--border)',
              borderRadius: '6px',
              padding: '6px 12px',
              color: 'var(--text-primary)',
              outline: 'none',
            }}
          >
            <option value="unlabeled">Unlabeled</option>
            <option value="idle">Idle</option>
            <option value="walk">Walking</option>
            <option value="wave">Waving</option>
            <option value="arm_raise">Arm Raise</option>
            <option value="grab">Grabbing</option>
            <option value="sit">Sitting</option>
            <option value="gesture">Gesture</option>
          </select>

          <button
            type="submit"
            disabled={loading}
            className="btn"
            style={{ width: 'auto', padding: '6px 16px' }}
          >
            {loading ? 'Saving...' : 'Save'}
          </button>
        </div>

        <textarea
          placeholder="Add session comments/notes..."
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          style={{
            background: 'var(--bg-tertiary)',
            border: '1px solid var(--border)',
            borderRadius: '6px',
            padding: '8px 12px',
            color: 'var(--text-primary)',
            outline: 'none',
            fontSize: '0.8rem',
            resize: 'vertical',
          }}
        />
      </form>
      {message && (
        <div style={{ marginTop: '8px', fontSize: '0.75rem', color: message.startsWith('✅') ? 'var(--accent)' : 'var(--danger)' }}>
          {message}
        </div>
      )}
    </div>
  )
}
