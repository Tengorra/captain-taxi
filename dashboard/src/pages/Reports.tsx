import { useState } from 'react'
import { useApi } from '../hooks/useApi'
import { api } from '../lib/api'
import { Download, FileText, Calendar } from 'lucide-react'
import { format, subDays } from 'date-fns'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'

export default function Reports() {
  const [startDate, setStartDate] = useState(format(subDays(new Date(), 30), 'yyyy-MM-dd'))
  const [endDate, setEndDate] = useState(format(new Date(), 'yyyy-MM-dd'))
  const [cityFilter, setCityFilter] = useState('')
  const [fetching, setFetching] = useState(false)
  const [reportData, setReportData] = useState<any>(null)

  const handleFetch = async () => {
    setFetching(true)
    try {
      const data = await api.revenueReport(startDate, endDate, cityFilter || undefined)
      setReportData(data)
    } finally {
      setFetching(false)
    }
  }

  const chartData = reportData
    ? Object.entries(reportData.daily as Record<string, { trips: number; revenue: number }>)
        .map(([date, d]) => ({
          date: format(new Date(date), 'MMM d'),
          revenue: d.revenue,
          trips: d.trips,
        }))
    : []

  return (
    <div className="space-y-5">

      {/* Report builder */}
      <div className="card">
        <h2 className="font-semibold text-sm text-gray-300 mb-4 flex items-center gap-2">
          <Calendar size={15} /> Revenue Report
        </h2>
        <div className="flex flex-wrap gap-3 items-end">
          <div>
            <label className="label">From</label>
            <input type="date" className="input" value={startDate}
              onChange={e => setStartDate(e.target.value)} />
          </div>
          <div>
            <label className="label">To</label>
            <input type="date" className="input" value={endDate}
              onChange={e => setEndDate(e.target.value)} />
          </div>
          <div>
            <label className="label">City</label>
            <select className="input" value={cityFilter} onChange={e => setCityFilter(e.target.value)}>
              <option value="">All Cities</option>
              <option value="saskatoon">Saskatoon</option>
              <option value="regina">Regina</option>
            </select>
          </div>
          <button onClick={handleFetch} className="btn-primary" disabled={fetching}>
            {fetching ? 'Loading...' : 'Generate Report'}
          </button>
        </div>
      </div>

      {/* Report results */}
      {reportData && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: 'Gross Revenue', value: `$${reportData.total_revenue.toLocaleString('en-CA', { minimumFractionDigits: 2 })}` },
              { label: 'Company Revenue', value: `$${reportData.company_revenue.toLocaleString('en-CA', { minimumFractionDigits: 2 })}` },
              { label: 'Driver Pay', value: `$${reportData.driver_pay.toLocaleString('en-CA', { minimumFractionDigits: 2 })}` },
              { label: 'Total Trips', value: reportData.total_trips.toString() },
            ].map(s => (
              <div key={s.label} className="card text-center">
                <p className="text-xl font-bold text-white">{s.value}</p>
                <p className="text-xs text-gray-500 mt-1">{s.label}</p>
              </div>
            ))}
          </div>

          {/* City breakdown */}
          {Object.keys(reportData.by_city).length > 0 && (
            <div className="grid grid-cols-2 gap-4">
              {Object.entries(reportData.by_city as Record<string, any>).map(([city, data]) => (
                <div key={city} className="card">
                  <h3 className="font-semibold text-sm capitalize text-gray-300 mb-2">{city}</h3>
                  <p className="text-xl font-bold text-white">
                    ${data.revenue.toLocaleString('en-CA', { minimumFractionDigits: 2 })}
                  </p>
                  <p className="text-xs text-gray-500">{data.trips} trips</p>
                </div>
              ))}
            </div>
          )}

          {/* Chart */}
          {chartData.length > 0 && (
            <div className="card">
              <h3 className="font-semibold text-sm text-gray-300 mb-4">Daily Revenue</h3>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={chartData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                  <XAxis dataKey="date" tick={{ fill: '#6b7280', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} axisLine={false} tickLine={false}
                    tickFormatter={v => `$${v}`} />
                  <Tooltip
                    contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8 }}
                    labelStyle={{ color: '#e5e7eb', fontSize: 12 }}
                    formatter={(v: number) => [`$${v.toFixed(2)}`, 'Revenue']}
                  />
                  <Line type="monotone" dataKey="revenue" stroke="#f59e0b" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}

      {/* Weekly PDF downloads */}
      <div className="card">
        <h2 className="font-semibold text-sm text-gray-300 mb-4 flex items-center gap-2">
          <FileText size={15} /> Weekly PDF Reports
        </h2>
        <div className="space-y-2">
          {[
            { label: 'Last Week', offset: 0 },
            { label: '2 Weeks Ago', offset: 1 },
            { label: '3 Weeks Ago', offset: 2 },
            { label: '4 Weeks Ago', offset: 3 },
          ].map(({ label, offset }) => (
            <div key={offset} className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0">
              <span className="text-sm text-gray-300">{label}</span>
              <a
                href={api.weeklyDownloadUrl(offset)}
                target="_blank"
                rel="noreferrer"
                className="btn-ghost text-xs"
              >
                <Download size={13} /> Download PDF
              </a>
            </div>
          ))}
        </div>
      </div>

    </div>
  )
}
