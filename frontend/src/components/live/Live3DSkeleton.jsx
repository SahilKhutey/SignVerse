import { Suspense, lazy } from 'react'

const ThreeViewer = lazy(() => import('./ThreeViewerInternal'))

export default function Live3DSkeleton(props) {
  return (
    <Suspense fallback={
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        height: '100%',
        color: '#9ca3c4',
        fontFamily: 'monospace',
        fontSize: 14,
        background: '#0a0e27',
        minHeight: 250,
      }}>
        Initializing 3D Visualizer...
      </div>
    }>
      <ThreeViewer {...props} />
    </Suspense>
  )
}

export { Live3DSkeleton }
