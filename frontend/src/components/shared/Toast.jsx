import { useUiStore } from '../../store/ui'

export function ToastContainer() {
  const toasts = useUiStore((s) => s.toasts)
  const removeToast = useUiStore((s) => s.removeToast)

  if (toasts.length === 0) return null

  return (
    <div className="toast-container">
      {toasts.map((t) => (
        <div 
          key={t.id} 
          className={`toast ${t.type}`}
          onClick={() => removeToast(t.id)}
          style={{ cursor: 'pointer' }}
        >
          <span>
            {t.type === 'success' && '✅'}
            {t.type === 'error' && '❌'}
            {t.type === 'info' && '🔔'}
          </span>
          <div>{t.message}</div>
        </div>
      ))}
    </div>
  )
}
export default ToastContainer
