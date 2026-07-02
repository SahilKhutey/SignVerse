import { useEffect, useState } from 'react'
import api from '../../api/client'
import { useUiStore } from '../../store/ui'
import { useSessionsStore } from '../../store/sessions'
import Button from '../shared/Button'

export default function IngestionQueue() {
  const [jobs, setJobs] = useState([])
  const [activeJobsCount, setActiveJobsCount] = useState(0)
  const addToast = useUiStore(s => s.addToast)
  const fetchSessions = useSessionsStore(s => s.fetchSessions)

  const loadJobs = async () => {
    try {
      const { data } = await api.get('/api/capture/jobs')
      setJobs(data)
      
      // Check if any job is currently active (queued, validating, processing)
      const activeCount = data.filter(j => 
        j.status === 'queued' || j.status === 'validating' || j.status === 'processing'
      ).length
      
      setActiveJobsCount(activeCount)
      
      // If we went from > 0 active jobs to 0, refresh sessions list
      if (activeCount === 0 && activeJobsCount > 0) {
        fetchSessions()
        addToast('Ingestion task completed. Refreshing sessions list.', 'success')
      }
    } catch (e) {
      console.error('Failed to load ingestion jobs', e)
    }
  }

  // Poll for jobs progress
  useEffect(() => {
    loadJobs()
    const interval = setInterval(loadJobs, 2000)
    return () => clearInterval(interval)
  }, [activeJobsCount])

  const handleCancel = async (jobId) => {
    try {
      await api.post(`/api/capture/jobs/${jobId}/cancel`)
      addToast('Ingestion task cancellation requested', 'info')
      loadJobs()
    } catch (e) {
      addToast('Failed to cancel job', 'error')
    }
  }

  if (jobs.length === 0) return null

  return (
    <div className="card" style={{ marginTop: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h3 className="card-title" style={{ margin: 0 }}>⚙️ Ingestion Task Queue</h3>
        {activeJobsCount > 0 && (
          <span style={{
            fontSize: 10,
            background: 'var(--accent)',
            color: '#fff',
            padding: '2px 8px',
            borderRadius: 12,
            fontWeight: 'bold',
          }}>
            Processing {activeJobsCount} Active
          </span>
        )}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {jobs.map((job) => {
          const isProcessing = job.status === 'queued' || job.status === 'validating' || job.status === 'processing'
          const pct = Math.round(job.progress * 100)
          
          let statusColor = 'var(--text-secondary)'
          let statusLabel = job.status.toUpperCase()
          if (job.status === 'processing') {
            statusColor = '#00d9ff'
            statusLabel = `Processing (${pct}%)`
          } else if (job.status === 'validating') {
            statusColor = '#ffcc00'
            statusLabel = 'Validating video'
          } else if (job.status === 'completed') {
            statusColor = '#00e676'
          } else if (job.status === 'failed') {
            statusColor = '#ff4400'
          } else if (job.status === 'cancelled') {
            statusColor = '#9e9e9e'
          }

          return (
            <div
              key={job.job_id}
              style={{
                background: 'var(--bg-tertiary)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                padding: '12px 16px',
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div style={{ fontSize: 11, fontWeight: 'bold', fontFamily: 'monospace' }}>
                    Job ID: {job.job_id} ({job.source_type})
                  </div>
                  <div style={{ fontSize: 10, color: statusColor, fontWeight: 700, marginTop: 2 }}>
                    Status: {statusLabel}
                  </div>
                </div>

                {isProcessing && (
                  <button
                    onClick={() => handleCancel(job.job_id)}
                    style={{
                      background: 'transparent',
                      border: '1px solid #ff4400',
                      color: '#ff4400',
                      borderRadius: 4,
                      fontSize: 10,
                      padding: '3px 8px',
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                    }}
                    onMouseOver={(e) => { e.target.style.background = 'rgba(255, 68, 0, 0.1)' }}
                    onMouseOut={(e) => { e.target.style.background = 'transparent' }}
                  >
                    Cancel
                  </button>
                )}
              </div>

              {isProcessing && (
                <div style={{ width: '100%', height: 6, background: 'var(--border)', borderRadius: 3, overflow: 'hidden' }}>
                  <div style={{
                    width: `${pct}%`,
                    height: '100%',
                    background: 'var(--accent)',
                    transition: 'width 0.3s ease',
                  }} />
                </div>
              )}

              {job.error && (
                <div style={{ fontSize: 10, color: '#ff4400', background: 'rgba(255, 68, 0, 0.05)', padding: '6px 10px', borderRadius: 4, fontFamily: 'monospace' }}>
                  Error: {job.error}
                </div>
              )}

              {job.status === 'completed' && job.session_id && (
                <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
                  Session ID: <span style={{ fontFamily: 'monospace', fontWeight: 'bold', color: '#fff' }}>{job.session_id}</span>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
export { IngestionQueue }
