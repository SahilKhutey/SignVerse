import { useRef, useEffect } from 'react'

export default function LiveInteractionLog({ frame }) {
  const logRef = useRef(null)
  const lastActionRef = useRef(null)
  
  useEffect(() => {
    if (!frame || !logRef.current) return
    
    const action = frame.primary_action
    const intent = frame.primary_intent
    const key = `${frame.frame_id}-${action}-${intent}`
    
    if (lastActionRef.current === key) return
    lastActionRef.current = key
    
    if (action === 'IDLE' && intent === 'IDLE') return
    
    const entry = document.createElement('div')
    const ts = new Date().toLocaleTimeString()
    entry.style.cssText = `
      padding: 6px 10px;
      margin-bottom: 4px;
      background: var(--bg-tertiary);
      border-left: 3px solid var(--accent);
      border-radius: 4px;
      font-size: 11px;
      font-family: monospace;
      animation: slideIn 0.3s ease;
    `
    entry.innerHTML = `
      <span style="color:var(--text-secondary)">${ts}</span> 
      <span style="color:var(--accent);font-weight:bold">${intent}</span> 
      <span style="color:var(--text-secondary)">·</span> 
      <span style="color:#10b981">${action}</span>
      <span style="color:var(--text-secondary)"> · frame ${frame.frame_id}</span>
    `
    
    // Remove default placeholder text if present
    const placeholder = logRef.current.querySelector('.placeholder-text')
    if (placeholder) {
      placeholder.remove()
    }
    
    logRef.current.prepend(entry)
    
    // Cap at 50 entries
    while (logRef.current.children.length > 50) {
      logRef.current.removeChild(logRef.current.lastChild)
    }
  }, [frame])
  
  return (
    <div style={{
      background: 'var(--bg-secondary)',
      borderRadius: 8,
      padding: 12,
      border: '1px solid var(--border)',
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
    }}>
      <div style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>
        📜 Interaction Log
      </div>
      <div ref={logRef} style={{ flex: 1, overflowY: 'auto' }}>
        <div className="placeholder-text" style={{ fontSize: 11, color: 'var(--text-secondary)', textAlign: 'center', padding: 20 }}>
          Events will appear here
        </div>
      </div>
      <style>{`@keyframes slideIn { from{opacity:0;transform:translateX(-10px)} to{opacity:1;transform:translateX(0)} }`}</style>
    </div>
  )
}
export { LiveInteractionLog }
