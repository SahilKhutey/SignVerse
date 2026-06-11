import { useState } from 'react'

const DEMO_STEPS = [
  {
    title: "1️⃣ Upload a Video",
    description: "Click 'Choose File' and select any video with human motion to process.",
    target: "upload-section",
  },
  {
    title: "2️⃣ Process Motion",
    description: "Click 'Process Video' to extract pose data using MediaPipe.",
    target: "process-button",
  },
  {
    title: "3️⃣ View 3D Skeleton",
    description: "Select your session in the Datasets Manager to see 3D playback and kinematics.",
    target: "dataset-list",
  },
  {
    title: "4️⃣ Detect Actions",
    description: "Click 'Detect Actions' under the timeline to auto-label motion segments.",
    target: "segment-button",
  },
  {
    title: "5️⃣ Export to Simulator",
    description: "Download BVH and import directly into Blender, or download the humanoid Robot trajectory.",
    target: "export-section",
  },
]

export default function DemoMode({ onStepClick }) {
  const [active, setActive] = useState(false)
  const [step, setStep] = useState(0)

  const next = () => {
    if (step < DEMO_STEPS.length - 1) {
      const newStep = step + 1
      setStep(newStep)
      onStepClick?.(DEMO_STEPS[newStep])
    } else {
      setActive(false)
      setStep(0)
    }
  }

  if (!active) {
    return (
      <button
        onClick={() => { setActive(true); onStepClick?.(DEMO_STEPS[0]) }}
        style={{
          position: 'fixed',
          bottom: '20px',
          right: '20px',
          padding: '12px 20px',
          background: 'linear-gradient(135deg, var(--accent), var(--accent-2))',
          color: '#0a0e17',
          border: 'none',
          borderRadius: '24px',
          cursor: 'pointer',
          fontWeight: 700,
          boxShadow: '0 4px 20px rgba(0, 217, 255, 0.4)',
          zIndex: 1000,
        }}
      >
        🎬 Start Demo Tour
      </button>
    )
  }

  return (
    <div style={{
      position: 'fixed',
      bottom: '20px',
      right: '20px',
      width: '320px',
      background: 'var(--bg-secondary)',
      border: '1px solid var(--accent)',
      borderRadius: '12px',
      padding: '1rem',
      boxShadow: '0 4px 20px rgba(0, 0, 0, 0.5)',
      zIndex: 1000,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
        <strong style={{ color: 'var(--accent)' }}>Demo Tour</strong>
        <button
          onClick={() => { setActive(false); setStep(0) }}
          style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}
        >
          ✕
        </button>
      </div>
      <h4 style={{ marginBottom: '4px' }}>{DEMO_STEPS[step].title}</h4>
      <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '12px' }}>
        {DEMO_STEPS[step].description}
      </p>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
          Step {step + 1} / {DEMO_STEPS.length}
        </span>
        <button
          onClick={next}
          className="btn"
          style={{ width: 'auto', padding: '6px 16px' }}
        >
          {step === DEMO_STEPS.length - 1 ? '✓ Finish' : 'Next →'}
        </button>
      </div>
    </div>
  )
}
