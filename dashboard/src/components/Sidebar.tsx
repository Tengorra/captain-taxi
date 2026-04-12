import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Car, Users, DollarSign,
  ShieldCheck, BarChart2, Settings, Menu, X
} from 'lucide-react'
import { useState } from 'react'
import clsx from 'clsx'

const NAV = [
  { to: '/overview',    icon: LayoutDashboard, label: 'Overview' },
  { to: '/dispatch',    icon: Car,             label: 'Dispatch' },
  { to: '/drivers',     icon: Users,           label: 'Drivers' },
  { to: '/accounts',    icon: DollarSign,      label: 'Accounts' },
  { to: '/compliance',  icon: ShieldCheck,     label: 'Compliance' },
  { to: '/reports',     icon: BarChart2,       label: 'Reports' },
  { to: '/settings',    icon: Settings,        label: 'Settings' },
]

interface Props {
  alertCount?: number
}

export default function Sidebar({ alertCount = 0 }: Props) {
  const [open, setOpen] = useState(false)

  return (
    <>
      {/* Mobile toggle */}
      <button
        className="fixed top-4 left-4 z-50 md:hidden btn-ghost p-2 rounded-lg"
        onClick={() => setOpen(!open)}
      >
        {open ? <X size={20} /> : <Menu size={20} />}
      </button>

      {/* Overlay */}
      {open && (
        <div
          className="fixed inset-0 bg-black/60 z-30 md:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={clsx(
        'fixed top-0 left-0 h-full w-60 bg-gray-900 border-r border-gray-800 z-40 flex flex-col',
        'transition-transform duration-200',
        open ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
      )}>
        {/* Logo */}
        <div className="px-5 py-5 border-b border-gray-800">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-amber-500 flex items-center justify-center text-gray-950 font-bold text-lg">
              🚕
            </div>
            <div>
              <p className="font-bold text-sm text-white">Captain Taxi</p>
              <p className="text-xs text-gray-500">Owner Dashboard</p>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              onClick={() => setOpen(false)}
              className={({ isActive }) => clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                isActive
                  ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                  : 'text-gray-400 hover:text-gray-100 hover:bg-gray-800'
              )}
            >
              <Icon size={18} />
              {label}
              {label === 'Overview' && alertCount > 0 && (
                <span className="ml-auto badge bg-red-500/20 text-red-400 border border-red-500/20">
                  {alertCount}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Cities indicator */}
        <div className="px-5 py-4 border-t border-gray-800">
          <p className="text-xs text-gray-600 mb-2 font-medium uppercase tracking-wide">Cities</p>
          <div className="flex gap-2">
            <span className="badge bg-gray-800 text-gray-300 border border-gray-700">Saskatoon</span>
            <span className="badge bg-gray-800 text-gray-300 border border-gray-700">Regina</span>
          </div>
        </div>
      </aside>
    </>
  )
}
