import React from 'react'

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('[ErrorBoundary] Error caught:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: '2rem',
          margin: '1.5rem',
          background: 'rgba(239, 68, 68, 0.15)',
          border: '1px solid var(--danger)',
          borderRadius: 8,
          color: 'var(--text-primary)',
        }}>
          <h3 style={{ marginBottom: '0.5rem', fontSize: 15 }}>⚠️ Component crashed</h3>
          <p style={{ fontSize: 12, color: 'var(--text-secondary)', fontFamily: 'monospace' }}>
            {this.state.error?.message || 'Unknown error'}
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            style={{
              marginTop: '1rem',
              padding: '6px 12px',
              background: 'var(--danger)',
              border: 'none',
              borderRadius: 4,
              color: 'white',
              fontSize: 12,
              cursor: 'pointer',
            }}
          >
            Retry Render
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
export default ErrorBoundary
