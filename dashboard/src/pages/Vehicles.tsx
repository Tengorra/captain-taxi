import { useState, useMemo } from 'react'
import { useApi } from '../hooks/useApi'
import { api } from '../lib/api'
import { Car, CheckCircle, XCircle } from 'lucide-react'
import clsx from 'clsx'

type VehicleRow = {
  id: string
  vehicle_ref?: string
  aka?: string
  plate?: string
  registration?: string
  make?: string
  model?: string
  color?: string
  year?: number
  city?: string
  is_active?: boolean
  is_deleted?: boolean
  insurer?: string
  insurance_expiry?: string
  plate_expiry?: string
  nct_mot_expiry?: string
  hire_expiry?: string
  council_compliance_expiry?: string
  wheelchair?: boolean
  executive?: boolean
  driver_id?: string
}

const PAGE_SIZE = 25

// Display ISO date/datetime as DD/MM/YYYY (iCabbi style)
function fmtDate(s?: string): string {
  if (!s) return '—'
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (!m) return s
  return `${m[3]}/${m[2]}/${m[1]}`
}

export default function Vehicles() {
  const [refQ, setRefQ]     = useState('')
  const [plateQ, setPlateQ] = useState('')
  const [makeQ, setMakeQ]   = useState('')
  const [activeF, setActiveF] = useState<'' | 'active' | 'inactive'>('')
  const [page, setPage]     = useState(1)
  const [applied, setApplied] = useState({ ref: '', plate: '', make: '', active: '' as '' | 'active' | 'inactive' })

  const { data: rows, loading } = useApi(
    () => api.listVehicles(
      applied.active === ''
        ? undefined
        : { active: applied.active === 'active' },
    ) as Promise<VehicleRow[]>,
    [applied],
  )

  const filtered = useMemo(() => {
    if (!rows) return []
    let r = [...rows]
    if (applied.ref) {
      const q = applied.ref.toLowerCase()
      r = r.filter(v =>
        (v.vehicle_ref || '').toLowerCase().includes(q) ||
        (v.id || '').toLowerCase().includes(q)
      )
    }
    if (applied.plate) {
      const q = applied.plate.toLowerCase()
      r = r.filter(v =>
        (v.plate || '').toLowerCase().includes(q) ||
        (v.registration || '').toLowerCase().includes(q)
      )
    }
    if (applied.make) {
      const q = applied.make.toLowerCase()
      r = r.filter(v =>
        (v.make || '').toLowerCase().includes(q) ||
        (v.model || '').toLowerCase().includes(q)
      )
    }
    r.sort((a, b) => (a.vehicle_ref || '').localeCompare(b.vehicle_ref || ''))
    return r
  }, [rows, applied])

  const total = filtered.length
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const paged = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  const handleSearch = () => {
    setApplied({ ref: refQ, plate: plateQ, make: makeQ, active: activeF })
    setPage(1)
  }

  const pageRange = () => {
    const start = Math.max(1, Math.min(page - 2, totalPages - 4))
    const end   = Math.min(totalPages, start + 4)
    return Array.from({ length: end - start + 1 }, (_, i) => start + i)
  }

  // Compliance highlight — flag rows where any tracked expiry is in the past.
  const isExpired = (s?: string): boolean => {
    if (!s) return false
    const t = Date.parse(s)
    return Number.isFinite(t) && t < Date.now()
  }

  return (
    <div className="card">
      <h1 className="text-lg font-semibold text-white mb-4 tracking-wide flex items-center gap-2">
        <Car size={18} /> Vehicles
      </h1>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        {[
          { label: 'REF',   value: refQ,   setter: setRefQ },
          { label: 'PLATE', value: plateQ, setter: setPlateQ },
          { label: 'MAKE',  value: makeQ,  setter: setMakeQ },
        ].map(({ label, value, setter }) => (
          <div key={label} className="flex items-center gap-2">
            <span className="text-xs text-gray-400 w-14 shrink-0 tracking-wide">{label}</span>
            <input
              className="input flex-1 text-sm"
              value={value}
              onChange={e => setter(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
            />
          </div>
        ))}
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400 w-14 shrink-0 tracking-wide">ACTIVE</span>
          <select
            className="input flex-1 text-sm"
            value={activeF}
            onChange={e => setActiveF(e.target.value as '' | 'active' | 'inactive')}
          >
            <option value="">ALL</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>
      </div>

      <div className="flex justify-end mb-4">
        <button onClick={handleSearch} className="btn-primary px-10 tracking-widest text-xs">
          SEARCH
        </button>
      </div>

      {!loading && (
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <p className="text-xs text-gray-400">
            Showing <span className="text-white font-medium">{total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1}</span> to <span className="text-white font-medium">{Math.min(page * PAGE_SIZE, total)}</span> of <span className="text-white font-medium">{total}</span> Vehicle(s)
          </p>
          {totalPages > 1 && (
            <div className="flex items-center gap-1 text-xs">
              <button onClick={() => setPage(1)} disabled={page === 1} className="px-2 py-1 rounded bg-gray-700 text-gray-300 disabled:opacity-30">First</button>
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="px-2 py-1 rounded bg-gray-700 text-gray-300 disabled:opacity-30">Prev</button>
              {pageRange().map(p => (
                <button key={p} onClick={() => setPage(p)} className={clsx('w-7 h-7 rounded font-semibold transition-colors', page === p ? 'bg-amber-500 text-black' : 'bg-gray-700 text-gray-300 hover:bg-gray-600')}>{p}</button>
              ))}
              <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} className="px-2 py-1 rounded bg-gray-700 text-gray-300 disabled:opacity-30">Next</button>
              <button onClick={() => setPage(totalPages)} disabled={page === totalPages} className="px-2 py-1 rounded bg-gray-700 text-gray-300 disabled:opacity-30">Last</button>
            </div>
          )}
        </div>
      )}

      <div className="overflow-x-auto">
        {loading ? (
          <div className="space-y-2 py-2">
            {Array.from({ length: 10 }).map((_, i) => (
              <div key={i} className="h-10 bg-gray-800 rounded animate-pulse" />
            ))}
          </div>
        ) : paged.length === 0 ? (
          <div className="text-center py-14 text-gray-600">
            <Car size={28} className="mx-auto mb-2" />
            <p className="text-sm">No vehicles found — import a fleet CSV from the Drivers page or adjust filters</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-800/60 border-b border-gray-700">
                {['REF', 'PLATE', 'MAKE', 'MODEL', 'COLOR', 'YEAR', 'INSURANCE EXP', 'PLATE EXP', 'NCT/MOT EXP', 'WHEELCHAIR', 'ACTIVE'].map(col => (
                  <th key={col} className="text-left px-3 py-2.5 text-xs font-semibold text-gray-400 tracking-widest uppercase whitespace-nowrap border-r border-gray-700/50 last:border-0">{col}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60">
              {paged.map(v => (
                <tr key={v.id} className={clsx('hover:bg-gray-800/40 transition-colors', v.is_deleted && 'opacity-50')}>
                  <td className="px-3 py-2.5 text-amber-300 font-mono text-xs whitespace-nowrap">{v.vehicle_ref || v.id.slice(0, 8).toUpperCase()}</td>
                  <td className="px-3 py-2.5 text-white font-mono text-xs whitespace-nowrap">{v.plate || '—'}</td>
                  <td className="px-3 py-2.5 text-gray-300 text-xs whitespace-nowrap">{v.make || '—'}</td>
                  <td className="px-3 py-2.5 text-gray-300 text-xs whitespace-nowrap">{v.model || '—'}</td>
                  <td className="px-3 py-2.5 text-gray-400 text-xs whitespace-nowrap">{v.color || '—'}</td>
                  <td className="px-3 py-2.5 text-gray-400 text-xs whitespace-nowrap">{v.year || '—'}</td>
                  <td className={clsx('px-3 py-2.5 text-xs whitespace-nowrap', isExpired(v.insurance_expiry) ? 'text-red-400' : 'text-gray-400')}>{fmtDate(v.insurance_expiry)}</td>
                  <td className={clsx('px-3 py-2.5 text-xs whitespace-nowrap', isExpired(v.plate_expiry) ? 'text-red-400' : 'text-gray-400')}>{fmtDate(v.plate_expiry)}</td>
                  <td className={clsx('px-3 py-2.5 text-xs whitespace-nowrap', isExpired(v.nct_mot_expiry) ? 'text-red-400' : 'text-gray-400')}>{fmtDate(v.nct_mot_expiry)}</td>
                  <td className="px-3 py-2.5 text-xs">
                    {v.wheelchair ? <CheckCircle size={14} className="text-emerald-400" /> : <span className="text-gray-700">—</span>}
                  </td>
                  <td className="px-3 py-2.5 text-xs">
                    {v.is_active ? <CheckCircle size={14} className="text-emerald-400" /> : <XCircle size={14} className="text-red-400/50" />}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
