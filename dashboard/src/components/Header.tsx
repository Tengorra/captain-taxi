import { Bell, RefreshCw } from 'lucide-react'
import { useLocation } from 'react-router-dom'

const PAGE_TITLES: Record<string, string> = {
  '/overview':   'Overview',
  '/dispatch':   'Dispatch',
  '/drivers':    'Drivers',
  '/accounts':   'Accounts',
  '/compliance': 'Compliance',
  '/reports':    'Reports',
  '/settings':   'Settings',
}

interface Props {
  alertCount?: number
  onRefresh?: () => void
  lastUpdated?: string
}

export default function Header({ alertCount = 0, onRefresh, lastUpdated }: Props) {
  const { pathname } = useLocation()
  const base = '/' + pathname.split('/')[1]
  const title = PAGE_TITLES[base] || 'Dashboard'

  return (
    <header className="h-14 bg-gray-900/80 backdrop-blur border-b border-gray-800 flex items-center justify-between px-5 sticky top-0 z-20">
      <h1 className="text-base font-semibold text-gray-100 ml-10 md:ml-0">{title}</h1>

      <div className="flex items-center gap-3">
        {lastUpdated && (
          <span className="hidden sm:block text-xs text-gray-500">
            Updated {lastUpdated}
          </span>
        )}

        {onRefresh && (
          <button onClick={onRefresh} className="btn-ghost p-2 rounded-lg" title="Refresh">
            <RefreshCw size={16} />
          </button>
        )}

        <button className="btn-ghost p-2 rounded-lg relative" title="Alerts">
          <Bell size={18} />
          {alertCount > 0 && (
            <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-red-500 rounded-full text-white text-[10px] flex items-center justify-center font-bold">
              {alertCount > 9 ? '9+' : alertCount}
            </span>
          )}
        </button>

        <div className="w-8 h-8 rounded-full bg-amber-500 flex items-center justify-center text-gray-950 text-xs font-bold">
          OW
        </div>
      </div>
    </header>
  )
}
