import { Outlet, Navigate } from 'react-router-dom'
import Sidebar from '../components/layout/Sidebar'
import TopBar from '../components/layout/TopBar'
import StatusBar from '../components/layout/StatusBar'
import { useAuthStore } from '../store/auth'
import ToastContainer from '../components/shared/Toast'

export default function DashboardLayout() {
  const token = useAuthStore((s) => s.token)

  if (!token) {
    return <Navigate to="/login" replace />
  }

  return (
    <div className="dashboard-layout">
      <Sidebar />
      <div className="main-content">
        <TopBar />
        <main className="page-container">
          <Outlet />
        </main>
        <StatusBar />
      </div>
      <ToastContainer />
    </div>
  )
}
export { DashboardLayout }
