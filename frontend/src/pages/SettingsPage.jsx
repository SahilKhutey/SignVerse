import { useState } from 'react'
import Button from '../components/shared/Button'
import { useUiStore } from '../store/ui'

export default function SettingsPage() {
  const [modelComplexity, setModelComplexity] = useState(1)
  const [minDetectionConfidence, setMinDetectionConfidence] = useState(0.5)
  const [minTrackingConfidence, setMinTrackingConfidence] = useState(0.5)
  const [targetFps, setTargetFps] = useState(30)
  const [enableSmoothing, setEnableSmoothing] = useState(true)
  const theme = useUiStore((s) => s.theme)
  const toggleTheme = useUiStore((s) => s.toggleTheme)

  const handleSave = () => {
    alert('Settings saved successfully!')
  }

  return (
    <div style={{ maxWidth: 600, display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div className="card">
        <h3 className="card-title">⚙️ General Settings</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>Theme Mode</div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Toggle between light and dark visual themes</div>
            </div>
            <Button variant="secondary" onClick={toggleTheme}>
              {theme === 'dark' ? '☀️ Light' : '🌙 Dark'}
            </Button>
          </div>
        </div>
      </div>

      <div className="card">
        <h3 className="card-title">🧠 Perception Configuration</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 12 }}>
          <div>
            <label className="label">Holistic Model Complexity: {modelComplexity}</label>
            <input
              type="range"
              min="0"
              max="2"
              step="1"
              value={modelComplexity}
              onChange={(e) => setModelComplexity(Number(e.target.value))}
              style={{ width: '100%', accentColor: 'var(--accent)' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-secondary)' }}>
              <span>0 (Fast)</span>
              <span>1 (Balanced)</span>
              <span>2 (Accurate)</span>
            </div>
          </div>

          <div>
            <label className="label">Min Detection Confidence: {minDetectionConfidence.toFixed(2)}</label>
            <input
              type="range"
              min="0.1"
              max="0.9"
              step="0.05"
              value={minDetectionConfidence}
              onChange={(e) => setMinDetectionConfidence(Number(e.target.value))}
              style={{ width: '100%', accentColor: 'var(--accent)' }}
            />
          </div>

          <div>
            <label className="label">Min Tracking Confidence: {minTrackingConfidence.toFixed(2)}</label>
            <input
              type="range"
              min="0.1"
              max="0.9"
              step="0.05"
              value={minTrackingConfidence}
              onChange={(e) => setMinTrackingConfidence(Number(e.target.value))}
              style={{ width: '100%', accentColor: 'var(--accent)' }}
            />
          </div>
        </div>
      </div>

      <div className="card">
        <h3 className="card-title">⚡ Ingestion & Frequency</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 12 }}>
          <div>
            <label className="label">Target Frame Rate: {targetFps} FPS</label>
            <select
              value={targetFps}
              onChange={(e) => setTargetFps(Number(e.target.value))}
              className="input"
              style={{ marginTop: 4 }}
            >
              <option value="15">15 FPS</option>
              <option value="30">30 FPS</option>
              <option value="60">60 FPS</option>
            </select>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <input
              type="checkbox"
              id="smoothing"
              checked={enableSmoothing}
              onChange={(e) => setEnableSmoothing(e.target.checked)}
              style={{ width: 16, height: 16, accentColor: 'var(--accent)' }}
            />
            <label htmlFor="smoothing" style={{ fontSize: 13, userSelect: 'none', cursor: 'pointer' }}>
              Enable skeletal coordinate smoothing (Kalman filter)
            </label>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 12 }}>
        <Button onClick={handleSave} style={{ flex: 1 }}>Save Changes</Button>
      </div>
    </div>
  )
}
export { SettingsPage }
