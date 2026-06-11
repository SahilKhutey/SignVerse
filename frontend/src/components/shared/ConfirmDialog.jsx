import Button from './Button'

export function ConfirmDialog({ 
  isOpen, 
  title, 
  message, 
  onConfirm, 
  onCancel, 
  confirmText = 'Confirm', 
  cancelText = 'Cancel',
  isDanger = false 
}) {
  if (!isOpen) return null

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <h3 style={{ fontSize: 16, color: 'var(--text-primary)', marginBottom: 10 }}>{title}</h3>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 20 }}>{message}</p>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
          <Button variant="secondary" onClick={onCancel}>{cancelText}</Button>
          <Button variant={isDanger ? 'danger' : 'primary'} onClick={onConfirm}>
            {confirmText}
          </Button>
        </div>
      </div>
    </div>
  )
}
export default ConfirmDialog
