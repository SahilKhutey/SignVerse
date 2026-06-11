import { Suspense, lazy } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import DashboardLayout from './pages/DashboardLayout'
import LoginPage from './pages/LoginPage'
import LivePage from './pages/LivePage'
import ErrorBoundary from './components/shared/ErrorBoundary'
import { LoadingSpinner } from './components/shared/LoadingSpinner'

// Lazy loaded heavy pages
const CapturePage = lazy(() => import('./pages/CapturePage'))
const DatasetsPage = lazy(() => import('./pages/DatasetsPage'))
const ViewerPage = lazy(() => import('./pages/ViewerPage'))
const ExportPage = lazy(() => import('./pages/ExportPage'))
const SystemPage = lazy(() => import('./pages/SystemPage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))

export default function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        
        <Route path="/" element={<DashboardLayout />}>
          <Route index element={<Navigate to="/capture" replace />} />
          <Route path="capture" element={
            <Suspense fallback={<PageLoader message="Loading capture panel..." />}>
              <CapturePage />
            </Suspense>
          } />
          <Route path="live" element={<LivePage />} />
          <Route path="datasets" element={
            <Suspense fallback={<PageLoader message="Loading dataset records..." />}>
              <DatasetsPage />
            </Suspense>
          } />
          <Route path="viewer" element={
            <Suspense fallback={<PageLoader message="Loading 3D viewer..." />}>
              <ViewerPage />
            </Suspense>
          } />
          <Route path="export" element={
            <Suspense fallback={<PageLoader message="Loading export engine..." />}>
              <ExportPage />
            </Suspense>
          } />
          <Route path="system" element={
            <Suspense fallback={<PageLoader message="Loading system settings..." />}>
              <SystemPage />
            </Suspense>
          } />
          <Route path="settings" element={
            <Suspense fallback={<PageLoader message="Loading settings..." />}>
              <SettingsPage />
            </Suspense>
          } />
          <Route path="*" element={<Navigate to="/capture" replace />} />
        </Route>
      </Routes>
    </ErrorBoundary>
  )
}

function PageLoader({ message }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '80vh' }}>
      <LoadingSpinner size={32} message={message} />
    </div>
  )
}
export { App }
