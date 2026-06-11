import { useState, useEffect } from 'react'
import { useSessionsStore } from '../../store/sessions'
import Button from '../shared/Button'

export default function LabelEditor({ sessionId, initialLabel }) {
  const [label, setLabel] = useState(initialLabel || '')
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const updateLabel = useSessionsStore(s => s.updateLabel)

  useEffect(() => {
    setLabel(initialLabel || '')
  }, [initialLabel])

  const handleSave = async () => {
    setSaving(true)
    try {
      await updateLabel(sessionId, label)
      setEditing(false)
    } catch (e) {
      console.error(e)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="card" style={{ padding: 12 }}>
      <h5 style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8, letterSpacing: 1 }}>🏷️ ACTION LABEL</h5>
      {editing ? (
        <div style={{ display: 'flex', gap: 6 }}>
          <input
            type="text"
            className="input"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            style={{ marginTop: 0, flex: 1, padding: '4px 8px', fontSize: 12 }}
            placeholder="Enter action label..."
            autoFocus
          />
          <Button size="sm" onClick={handleSave} disabled={saving}>
            {saving ? '...' : 'Save'}
          </Button>
          <Button size="sm" variant="secondary" onClick={() => { setLabel(initialLabel || ''); setEditing(false) }}>
            Cancel
          </Button>
        </div>
      ) : (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 13, color: label ? 'var(--accent)' : 'var(--text-secondary)', fontWeight: 600 }}>
            {label || 'No label set'}
          </span>
          <button
            onClick={() => setEditing(true)}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--accent)',
              cursor: 'pointer',
              fontSize: 11,
              fontWeight: 600,
            }}
          >
            ✏️ Edit
          </button>
        </div>
      )}
    </div>
  )
}
export { LabelEditor }
