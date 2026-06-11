import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useSessionsStore } from '../store/sessions'
import { EXPORT_FORMATS } from '../utils/constants'
import FormatCard from '../components/export/FormatCard'
import UsageGuide from '../components/export/UsageGuide'
import api from '../api/client'
import { useUiStore } from '../store/ui'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { EmptyState } from '../components/shared/EmptyState'

export default function ExportPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const sessionId = searchParams.get('session')
  const { sessions, fetchSessions } = useSessionsStore()
  const addToast = useUiStore(s => s.addToast)

  useEffect(() => {
    fetchSessions()
  }, [])

  const handleSelectSession = (id) => {
    setSearchParams({ session: id })
  }

  const handleDownload = async (formatId) => {
    if (!sessionId) return
    addToast(`Generating and downloading ${formatId.toUpperCase()}...`, 'info')
    try {
      const response = await api.get(`/api/exporters/${sessionId}/export?format=${formatId}`, {
        responseType: 'blob',
      })
      const blob = new Blob([response.data], { type: response.headers['content-type'] })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      const disposition = response.headers['content-disposition']
      let filename = `export_${sessionId}.${formatId}`
      if (disposition && disposition.indexOf('filename=') !== -1) {
        const matches = disposition.match(/filename="?([^"]+)"?/)
        if (matches && matches[1]) filename = matches[1]
      }
      link.setAttribute('download', filename)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      addToast('Download completed!', 'success')
    } catch (err) {
      addToast(`Export failed: ${err.message}`, 'error')
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Session Selection Header */}
      <div className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 13, fontWeight: 600 }}>📦 Active Session:</span>
          <select
            className="input"
            value={sessionId || ''}
            onChange={(e) => handleSelectSession(e.target.value)}
            style={{ marginTop: 0, padding: '4px 8px', width: 220, fontSize: 12 }}
          >
            <option value="">-- Choose Session --</option>
            {sessions.map(s => (
              <option key={s.session_id} value={s.session_id}>
                {s.session_id} ({s.action_label || 'unlabeled'})
              </option>
            ))}
          </select>
        </div>
        {sessionId && (
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
            Session ID: <strong style={{ fontFamily: 'monospace' }}>{sessionId}</strong>
          </div>
        )}
      </div>

      {sessionId ? (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 20 }}>
          {/* Format selection grid */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <h3 style={{ fontSize: 14, color: 'var(--text-primary)' }}>Select Export Format</h3>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
              gap: 12,
            }}>
              {EXPORT_FORMATS.map(f => (
                <FormatCard
                  key={f.id}
                  format={f}
                  onClick={() => handleDownload(f.id)}
                />
              ))}
            </div>
          </div>

          {/* Quick usage guide */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <UsageGuide />
          </div>
        </div>
      ) : (
        <EmptyState
          icon="📦"
          title="Select a Session"
          description="Choose a captured motion session from the dropdown above to view export formats."
        />
      )}
    </div>
  )
}
export { ExportPage }
