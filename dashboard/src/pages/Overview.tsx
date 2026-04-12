import { Users, Car, DollarSign, Bell, AlertTriangle, CheckCircle, XCircle } from 'lucide-react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'
import { useApi, useMutation } from '../hooks/useApi'
import { api } from '../lib/api'
import StatCard from '../components/StatCard'
import EscalationCard from '../components/EscalationCard'
import { formatDistanceToNow } from 'date-fns'
import clsx from 'clsx'

export default function Overview() {
  const { data: overview, loading: ovLoading, reload: reloadOv } = useApi(
    () => api.overview(), [], { interval: 15_000 }
  )
  const { data: alerts, reload: reloadAlerts } = useApi(
    () => api.alerts(10), [], { interval: 20_000 }
  )
  const { data: chart } = useApi(() => api.revenueChart(7), [])
  const { data: escalations, reload: reloadEsc } = useApi(
    () => api.listEscalations('pending'), [], { interval: 20_000 }
  )

  const { mutate: decide, loading: deciding } = useMutation(
    (id: number, decision: 'approved' | 'denied') => api.decideEscalation(id, decision)
  )

  const handleDecide = async (id: number, decision: 'approved' | 'denied') => {
    await decide(id, decision)
    reloadEsc()
    reloadOv()
  }

  const { mutate: resolveAlert } = useMutation((id: number) => api.resolveAlert(id))

  const handleResolveAlert = async (id: number) => {
    await resolveAlert(id)
    reloadAlerts()
    reloadOv()
  }

  const severityColor: Record<string, string> = {
    low: 'text-gray-400',
    medium: 'text-amber-400',
    high: 'text-orange-400',
    critical: 'text-red-400',
  }

  const severityBg: Record<string, string> = {
    low: 'bg-gray-700/40 border-gray-700',
    medium: 'bg-amber-500/5 border-amber-500/20',
    high: 'bg-orange-500/5 border-orange-500/20',
    critical: 'bg-red-500/10 border-red-500/30',
  }

  return (
    <div className="space-y-6">

      {/* Stats row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Drivers Online"
          value={overview?.drivers_online.total ?? '—'}
          sub={`${overview?.drivers_online.saskatoon ?? 0} SK · ${overview?.drivers_online.regina ?? 0} RG`}
          icon={Users}
          iconColor="text-emerald-400"
          loading={ovLoading}
        />
        <StatCard
          label="Active Trips"
          value={overview?.active_trips.total ?? '—'}
          sub={`${overview?.active_trips.saskatoon ?? 0} SK · ${overview?.active_trips.regina ?? 0} RG`}
          icon={Car}
          iconColor="text-blue-400"
          loading={ovLoading}
        />
        <StatCard
          label="Today's Revenue"
          value={overview ? `$${overview.today.revenue.toLocaleString('en-CA', { minimumFractionDigits: 2 })}` : '—'}
          sub={`${overview?.today.trips ?? 0} trips`}
          icon={DollarSign}
          iconColor="text-amber-400"
          change={overview?.today.revenue_change_pct}
          loading={ovLoading}
        />
        <StatCard
          label="Alerts"
          value={overview?.alerts.unread ?? '—'}
          sub={`${overview?.pending_escalations ?? 0} escalations pending`}
          icon={Bell}
          iconColor="text-red-400"
          invertChange
          loading={ovLoading}
        />
      </div>

      {/* Revenue chart + Escalations */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* 7-day revenue chart */}
        <div className="card lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-sm text-gray-200">Revenue — Last 7 Days</h2>
          </div>
          {chart && chart.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={chart} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="revenueGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis dataKey="label" tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false}
                  tickFormatter={(v) => `$${v}`} />
                <Tooltip
                  contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8 }}
                  labelStyle={{ color: '#e5e7eb', fontSize: 12 }}
                  itemStyle={{ color: '#f59e0b', fontSize: 12 }}
                  formatter={(v: number) => [`$${v.toFixed(2)}`, 'Revenue']}
                />
                <Area type="monotone" dataKey="revenue" stroke="#f59e0b" strokeWidth={2}
                  fill="url(#revenueGrad)" dot={false} activeDot={{ r: 4, fill: '#f59e0b' }} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-48 flex items-center justify-center text-gray-600 text-sm">
              No revenue data yet
            </div>
          )}
        </div>

        {/* Pending escalations */}
        <div className="card flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-sm text-gray-200">Pending Escalations</h2>
            {escalations && escalations.length > 0 && (
              <span className="badge bg-amber-500/10 text-amber-400 border border-amber-500/20">
                {escalations.length}
              </span>
            )}
          </div>
          <div className="flex-1 overflow-y-auto space-y-3 max-h-56">
            {!escalations || escalations.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-32 text-gray-600">
                <CheckCircle size={28} className="mb-2 text-emerald-700" />
                <p className="text-sm">No pending escalations</p>
              </div>
            ) : (
              escalations.map(esc => (
                <EscalationCard
                  key={esc.id}
                  escalation={esc}
                  onApprove={(id) => handleDecide(id, 'approved')}
                  onDeny={(id) => handleDecide(id, 'denied')}
                  loading={deciding}
                />
              ))
            )}
          </div>
        </div>
      </div>

      {/* Alert inbox */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-sm text-gray-200">Alert Inbox</h2>
          {alerts && alerts.filter(a => !a.is_read).length > 0 && (
            <span className="badge bg-red-500/10 text-red-400 border border-red-500/20">
              {alerts.filter(a => !a.is_read).length} unread
            </span>
          )}
        </div>
        {!alerts || alerts.length === 0 ? (
          <div className="text-center py-8 text-gray-600">
            <CheckCircle size={32} className="mx-auto mb-2 text-emerald-800" />
            <p className="text-sm">All clear — no alerts</p>
          </div>
        ) : (
          <div className="space-y-2">
            {alerts.map(alert => (
              <div
                key={alert.id}
                className={clsx(
                  'flex items-start gap-3 p-3 rounded-lg border transition-opacity',
                  severityBg[alert.severity],
                  alert.is_read && 'opacity-50'
                )}
              >
                <AlertTriangle size={16} className={clsx('flex-shrink-0 mt-0.5', severityColor[alert.severity])} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <p className="text-sm font-medium text-gray-200">{alert.title}</p>
                    <span className="text-xs text-gray-600 capitalize">{alert.source_agent}</span>
                  </div>
                  <p className="text-xs text-gray-400">{alert.message}</p>
                  <p className="text-xs text-gray-600 mt-1">
                    {formatDistanceToNow(new Date(alert.created_at), { addSuffix: true })}
                  </p>
                </div>
                <button
                  onClick={() => handleResolveAlert(alert.id)}
                  className="flex-shrink-0 text-gray-600 hover:text-emerald-400 transition-colors"
                  title="Resolve"
                >
                  <XCircle size={16} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

    </div>
  )
}
