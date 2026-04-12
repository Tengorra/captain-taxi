import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'
import { useApi } from '../hooks/useApi'
import { api } from '../lib/api'

export default function Layout() {
  const { data: overview, reload } = useApi(
    () => api.overview(),
    [],
    { interval: 30_000 }
  )

  const alertCount = (overview?.alerts.unread ?? 0) + (overview?.pending_escalations ?? 0)

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar alertCount={alertCount} />

      <div className="flex-1 flex flex-col overflow-hidden md:ml-60">
        <Header
          alertCount={alertCount}
          onRefresh={reload}
          lastUpdated={overview ? new Date(overview.timestamp).toLocaleTimeString() : undefined}
        />
        <main className="flex-1 overflow-y-auto p-5">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
