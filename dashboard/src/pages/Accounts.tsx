import { useState } from 'react'
import { useApi } from '../hooks/useApi'
import { api } from '../lib/api'
import { DollarSign, TrendingUp, Users, Download } from 'lucide-react'
import { format, subDays, startOfWeek, endOfWeek, startOfMonth, endOfMonth } from 'date-fns'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts'

type Period = 'week' | 'month' | 'custom'

export default function Accounts() {
  const [period, setPeriod] = useState<Period>('week')
  const [customStart, setCustomStart] = useState(format(subDays(new Date(), 7), 'yyyy-MM-dd'))
  const [customEnd, setCustomEnd] = useState(format(new Date(), 'yyyy-MM-dd'))

  const getDateRange = () => {
    const now = new Date()
    if (period === 'week') {
      return {
        start: format(startOfWeek(now, { weekStartsOn: 1 }), 'yyyy-MM-dd'),
        end: format(endOfWeek(now, { weekStartsOn: 1 }), 'yyyy-MM-dd'),
      }
    }
    if (period === 'month') {
      return {
        start: format(startOfMonth(now), 'yyyy-MM-dd'),
        end: format(endOfMonth(now), 'yyyy-MM-dd'),
      }
    }
    return { start: customStart, end: customEnd }
  }

  const { start, end } = getDateRange()

  const { data: report, loading } = useApi(
    () => api.revenueReport(start, end),
    [start, end]
  )

  // Build chart data from daily
  const chartData = report
    ? Object.entries(report.daily).map(([date, d]) => ({
        date: format(new Date(date), 'MMM d'),
        revenue: d.revenue,
        trips: d.trips,
      }))
    : []

  const handleDownload = () => {
    window.open(api.weeklyDownloadUrl(0), '_blank')
  }

  return (
    <div className="space-y-5">

      {/* Period selector */}
      <div className="flex flex-wrap gap-3 items-end">
        <div className="flex gap-2">
          {(['week', 'month', 'custom'] as Period[]).map(p => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-colors
                ${period === p ? 'bg-amber-500 text-gray-950' : 'bg-gray-800 text-gray-400 hover:text-gray-200'}`}
            >
              {p === 'week' ? 'This Week' : p === 'month' ? 'This Month' : 'Custom'}
            </button>
          ))}
        </div>
        {period === 'custom' && (
          <div className="flex gap-2 items-center">
            <input type="date" className="input w-36" value={customStart}
              onChange={e => setCustomStart(e.target.value)} />
            <span className="text-gray-500 text-sm">to</span>
            <input type="date" className="input w-36" value={customEnd}
              onChange={e => setCustomEnd(e.target.value)} />
          </div>
        )}
        <button onClick={handleDownload} className="btn-ghost ml-auto">
          <Download size={15} /> Download PDF
        </button>
      </div>

      {/* Revenue summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          {
            label: 'Gross Revenue',
            value: loading ? '—' : `$${(report?.total_revenue ?? 0).toLocaleString('en-CA', { minimumFractionDigits: 2 })}`,
            icon: DollarSign,
            color: 'text-amber-400',
          },
          {
            label: 'Company Revenue',
            value: loading ? '—' : `$${(report?.company_revenue ?? 0).toLocaleString('en-CA', { minimumFractionDigits: 2 })}`,
            icon: TrendingUp,
            color: 'text-emerald-400',
            sub: '30% commission',
          },
          {
            label: 'Driver Pay',
            value: loading ? '—' : `$${(report?.driver_pay ?? 0).toLocaleString('en-CA', { minimumFractionDigits: 2 })}`,
            icon: Users,
            color: 'text-blue-400',
            sub: '70% to drivers',
          },
          {
            label: 'Total Trips',
            value: loading ? '—' : (report?.total_trips ?? 0).toString(),
            icon: TrendingUp,
            color: 'text-purple-400',
          },
        ].map(card => (
          <div key={card.label} className="card flex items-start gap-3">
            <div className={`p-2.5 rounded-lg bg-gray-800 ${card.color}`}>
              <card.icon size={18} />
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">{card.label}</p>
              <p className="text-xl font-bold text-white">{card.value}</p>
              {card.sub && <p className="text-xs text-gray-500 mt-0.5">{card.sub}</p>}
            </div>
          </div>
        ))}
      </div>

      {/* By city breakdown */}
      {report?.by_city && Object.keys(report.by_city).length > 0 && (
        <div className="grid grid-cols-2 gap-4">
          {Object.entries(report.by_city).map(([city, data]) => (
            <div key={city} className="card">
              <h3 className="font-semibold text-sm text-gray-300 capitalize mb-3">{city}</h3>
              <div className="flex justify-between">
                <div>
                  <p className="text-2xl font-bold text-white">
                    ${data.revenue.toLocaleString('en-CA', { minimumFractionDigits: 2 })}
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5">{data.trips} trips</p>
                </div>
                <div className="text-right">
                  <p className="text-sm text-emerald-400 font-semibold">
                    ${(data.revenue * 0.3).toLocaleString('en-CA', { minimumFractionDigits: 2 })}
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5">Company</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Revenue chart */}
      <div className="card">
        <h2 className="font-semibold text-sm text-gray-300 mb-5">Daily Revenue Breakdown</h2>
        {chartData.length === 0 ? (
          <div className="h-48 flex items-center justify-center text-gray-600 text-sm">
            No data for this period
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={chartData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="date" tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false}
                tickFormatter={(v) => `$${v}`} />
              <Tooltip
                contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8 }}
                labelStyle={{ color: '#e5e7eb', fontSize: 12 }}
                formatter={(v: number, name: string) =>
                  name === 'revenue' ? [`$${v.toFixed(2)}`, 'Revenue'] : [v, 'Trips']
                }
              />
              <Bar dataKey="revenue" fill="#f59e0b" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* QuickBooks sync note */}
      <div className="card border-dashed border-gray-700 bg-gray-900/30">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded bg-green-600/10 flex items-center justify-center text-green-400 text-sm font-bold">QB</div>
          <div>
            <p className="text-sm font-medium text-gray-300">QuickBooks Sync</p>
            <p className="text-xs text-gray-500">QuickBooks Online integration — connect via Settings to enable auto-sync</p>
          </div>
          <button className="ml-auto btn-ghost text-xs">Configure</button>
        </div>
      </div>

    </div>
  )
}
