import { useEffect, useState } from 'react'
import { useSessionsStore } from '../store/sessions'
import DatasetGrid from '../components/dataset/DatasetGrid'
import SessionDetail from '../components/dataset/SessionDetail'
import DatasetStats from '../components/dataset/DatasetStats'
import ConfirmDialog from '../components/shared/ConfirmDialog'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import Button from '../components/shared/Button'

export default function DatasetsPage() {
  const { 
    sessions, 
    selectedId, 
    currentSession, 
    loading, 
    stats, 
    fetchSessions, 
    fetchStats, 
    selectSession,
    deleteSession 
  } = useSessionsStore()

  const [search, setSearch] = useState('')
  const [filterType, setFilterType] = useState('all')
  const [sessionToDelete, setSessionToDelete] = useState(null)

  useEffect(() => {
    fetchSessions()
    fetchStats()
  }, [])

  const filteredSessions = sessions.filter(s => {
    const matchesSearch = s.session_id.toLowerCase().includes(search.toLowerCase()) || 
                          (s.action_label || '').toLowerCase().includes(search.toLowerCase())
    const matchesType = filterType === 'all' || s.source_type === filterType
    return matchesSearch && matchesType
  })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, height: 'calc(100vh - 120px)' }}>
      <DatasetStats stats={stats} />

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: 20, flex: 1, overflow: 'hidden' }}>
        {/* Left Side: Sessions Grid */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, overflow: 'hidden' }}>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <input
              type="text"
              className="input"
              placeholder="🔍 Search session ID or label..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ marginTop: 0, flex: 1 }}
            />
            <select
              className="input"
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              style={{ marginTop: 0, width: 140 }}
            >
              <option value="all">All Sources</option>
              <option value="upload">Uploads</option>
              <option value="youtube">YouTube</option>
              <option value="camera">Webcam</option>
              <option value="demo">Demo</option>
            </select>
            <Button variant="secondary" onClick={() => { fetchSessions(); fetchStats() }}>
              🔄 Refresh
            </Button>
          </div>

          <div style={{ flex: 1, overflowY: 'auto' }}>
            {loading && sessions.length === 0 ? (
              <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem' }}>
                <LoadingSpinner message="Loading sessions..." />
              </div>
            ) : (
              <DatasetGrid
                sessions={filteredSessions}
                selectedId={selectedId}
                onSelect={selectSession}
                onDelete={(id) => setSessionToDelete(id)}
              />
            )}
          </div>
        </div>

        {/* Right Side: Detail Panel */}
        <div style={{ overflowY: 'auto', background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 12, padding: 16 }}>
          <SessionDetail 
            session={currentSession} 
            loading={loading && selectedId !== null} 
          />
        </div>
      </div>

      <ConfirmDialog
        isOpen={sessionToDelete !== null}
        title="⚠️ Delete Session"
        message="Are you sure you want to permanently delete this motion session and all its associated coordinates and frames?"
        onConfirm={async () => {
          if (sessionToDelete) {
            await deleteSession(sessionToDelete)
            setSessionToDelete(null)
          }
        }}
        onCancel={() => setSessionToDelete(null)}
        isDanger={true}
        confirmText="Delete permanently"
      />
    </div>
  )
}
export { DatasetsPage }
