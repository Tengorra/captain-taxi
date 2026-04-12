import clsx from 'clsx'
import type { LucideIcon } from 'lucide-react'
import { TrendingUp, TrendingDown } from 'lucide-react'

interface Props {
  label: string
  value: string | number
  sub?: string
  icon?: LucideIcon
  iconColor?: string
  change?: number        // percent change, positive = good
  invertChange?: boolean // e.g. for alerts — lower is better
  loading?: boolean
}

export default function StatCard({
  label, value, sub, icon: Icon, iconColor = 'text-amber-400',
  change, invertChange, loading
}: Props) {
  const isPositive = invertChange ? (change ?? 0) < 0 : (change ?? 0) > 0
  const isNegative = invertChange ? (change ?? 0) > 0 : (change ?? 0) < 0

  return (
    <div className="card flex items-start gap-4">
      {Icon && (
        <div className={clsx('p-2.5 rounded-lg bg-gray-800', iconColor)}>
          <Icon size={20} />
        </div>
      )}
      <div className="flex-1 min-w-0">
        <p className="text-xs text-gray-500 font-medium mb-1">{label}</p>
        {loading ? (
          <div className="h-7 w-20 bg-gray-800 rounded animate-pulse" />
        ) : (
          <p className="text-2xl font-bold text-white leading-tight">{value}</p>
        )}
        <div className="flex items-center gap-2 mt-1">
          {sub && <p className="text-xs text-gray-500">{sub}</p>}
          {change !== undefined && change !== 0 && (
            <span className={clsx(
              'flex items-center gap-0.5 text-xs font-medium',
              isPositive && 'text-emerald-400',
              isNegative && 'text-red-400',
              !isPositive && !isNegative && 'text-gray-500',
            )}>
              {isPositive ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
              {Math.abs(change)}%
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
