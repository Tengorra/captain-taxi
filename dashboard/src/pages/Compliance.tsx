import { useApi } from '../hooks/useApi'
import { api } from '../lib/api'
import { ShieldCheck, AlertTriangle, XCircle, Clock } from 'lucide-react'
import clsx from 'clsx'
import { format } from 'date-fns'

const DOC_LABELS: Record<string, string> = {
  license: 'License',
  abstract: 'Abstract',
  insurance: 'Insurance',
  taxi_permit: 'Taxi Permit',
  vehicle_inspection: 'Inspection',
}

const DOC_KEYS = Object.keys(DOC_LABELS)

export default function Compliance() {
  const { data: overview, loading } = useApi(() => api.complianceOverview(), [], { interval: 60_000 })
  const { data: expiring } = useApi(() => api.expiringDocs(30), [])

  const green = overview?.filter(d => d.overall_status === 'green').length ?? 0
  const amber = overview?.filter(d => d.overall_status === 'amber').length ?? 0
  const red = overview?.filter(d => d.overall_status === 'red').length ?? 0

  const cellColor = (status: string) => {
    switch (status) {
      case 'valid':         return 'bg-emerald-500 rounded-full'
      case 'expiring':      return 'bg-amber-400 rounded-full'
      case 'expiring_soon': return 'bg-orange-500 rounded-full'
      case 'expired':       return 'bg-red-500 rounded-full'
      case 'missing':       return 'bg-gray-600 rounded-full'
      default:              return 'bg-gray-700 rounded-full'
    }
  }

  const rowBorder = (status: string) => {
    if (status === 'red')   return 'border-l-4 border-l-red-500'
    if (status === 'amber') return 'border-l-4 border-l-amber-500'
    return ''
  }

  return (
    <div className="space-y-5">

      {/* Summary traffic lights */}
      <div className="grid grid-cols-3 gap-4">
        <div className="card flex items-center gap-3">
          <div className="w-4 h-4 rounded-full bg-emerald-500 flex-shrink-0" />
          <div>
            <p className="text-2xl font-bold text-emerald-400">{green}</p>
            <p className="text-xs text-gray-500">Fully compliant</p>
          </div>
        </div>
        <div className="card flex items-center gap-3">
          <div className="w-4 h-4 rounded-full bg-amber-500 flex-shrink-0" />
          <div>
            <p className="text-2xl font-bold text-amber-400">{amber}</p>
            <p className="text-xs text-gray-500">Expiring soon</p>
          </div>
        </div>
        <div className="card flex items-center gap-3">
          <div className="w-4 h-4 rounded-full bg-red-500 flex-shrink-0" />
          <div>
            <p className="text-2xl font-bold text-red-400">{red}</p>
            <p className="text-xs text-gray-500">Action required</p>
          </div>
        </div>
      </div>

      {/* Expiring soon list */}
      {expiring && Array.isArray(expiring) && expiring.length > 0 && (
        <div className="card border border-amber-500/20 bg-amber-500/5">
          <h2 className="font-semibold text-sm text-amber-400 mb-3 flex items-center gap-2">
            <Clock size={15} /> Expiring Within 30 Days ({expiring.length})
          </h2>
          <div className="space-y-2">
            {(expiring as any[]).slice(0, 8).map((item: any) => (
              <div key={item.document_id} className="flex items-center justify-between text-sm py-1 border-b border-amber-500/10 last:border-0">
                <div>
                  <span className="font-medium text-gray-200">{item.driver_name}</span>
                  <span className="text-gray-500 ml-2 capitalize">{item.city}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-gray-400 text-xs">{item.doc_type.replace('_', ' ')}</span>
                  <span className={clsx('badge text-xs', {
                    'bg-red-500/10 text-red-400 border border-red-500/20': item.status === 'expired',
                    'bg-orange-500/10 text-orange-400': item.days_until_expiry < 7,
                    'bg-amber-500/10 text-amber-400': item.days_until_expiry >= 7,
                  })}>
                    {item.days_until_expiry < 0
                      ? 'EXPIRED'
                      : `${item.days_until_expiry}d`}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Full traffic light grid */}
      <div className="card p-0 overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-800 flex items-center gap-2">
          <ShieldCheck size={15} className="text-gray-400" />
          <span className="text-sm font-semibold text-gray-300">Driver Compliance Overview</span>
        </div>

        {loading ? (
          <div className="p-6 space-y-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-10 bg-gray-800 rounded animate-pulse" />
            ))}
          </div>
        ) : !overview || overview.length === 0 ? (
          <div className="text-center py-12 text-gray-600">No drivers found</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-xs text-gray-500 uppercase tracking-wide">
                  <th className="text-left px-5 py-3 font-medium">Driver</th>
                  <th className="text-left px-4 py-3 font-medium hidden sm:table-cell">City</th>
                  {DOC_KEYS.map(key => (
                    <th key={key} className="text-center px-3 py-3 font-medium hidden md:table-cell">
                      {DOC_LABELS[key]}
                    </th>
                  ))}
                  <th className="text-center px-4 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/50">
                {overview.map(driver => (
                  <tr key={driver.driver_id} className={clsx('hover:bg-gray-800/30', rowBorder(driver.overall_status))}>
                    <td className="px-5 py-3 font-medium text-white">{driver.driver_name}</td>
                    <td className="px-4 py-3 hidden sm:table-cell capitalize text-gray-400">{driver.city}</td>
                    {DOC_KEYS.map(key => (
                      <td key={key} className="px-3 py-3 hidden md:table-cell text-center">
                        <div className="flex justify-center">
                          <div
                            className={clsx('w-3 h-3', cellColor(driver.documents[key] || 'missing'))}
                            title={driver.documents[key] || 'missing'}
                          />
                        </div>
                      </td>
                    ))}
                    <td className="px-4 py-3 text-center">
                      <div className="flex justify-center">
                        <div className={clsx('w-3 h-3 rounded-full', {
                          'bg-emerald-500': driver.overall_status === 'green',
                          'bg-amber-500': driver.overall_status === 'amber',
                          'bg-red-500': driver.overall_status === 'red',
                        })} />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Legend */}
        <div className="px-5 py-3 border-t border-gray-800 flex gap-4 text-xs text-gray-500">
          {[
            { color: 'bg-emerald-500', label: 'Valid' },
            { color: 'bg-amber-400', label: 'Expiring (30d)' },
            { color: 'bg-orange-500', label: 'Expiring soon (14d)' },
            { color: 'bg-red-500', label: 'Expired' },
            { color: 'bg-gray-600', label: 'Missing' },
          ].map(({ color, label }) => (
            <span key={label} className="flex items-center gap-1">
              <span className={clsx('w-2.5 h-2.5 rounded-full inline-block', color)} />
              {label}
            </span>
          ))}
        </div>
      </div>

    </div>
  )
}
