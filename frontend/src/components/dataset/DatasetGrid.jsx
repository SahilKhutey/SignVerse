import SessionCard from './SessionCard'
import { EmptyState } from '../shared/EmptyState'

export default function DatasetGrid({ sessions, selectedId, onSelect, onDelete }) {
  if (sessions.length === 0) {
    return (
      <EmptyState
        icon="📂"
        title="No Sessions Found"
        description="Try clearing your search filters or record/upload a new session."
      />
    )
  }

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fill, minmax(230px, 1fr))',
      gap: 12,
    }}>
      {sessions.map((session) => (
        <SessionCard
          key={session.session_id}
          session={session}
          isSelected={session.session_id === selectedId}
          onSelect={onSelect}
          onDelete={onDelete}
        />
      ))}
    </div>
  )
}
export { DatasetGrid }
