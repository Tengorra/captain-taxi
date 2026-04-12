import { useState, useEffect, useRef, useCallback } from 'react'
import { useApi } from '../hooks/useApi'
import { api } from '../lib/api'
import {
  DispatchTrip, DispatchDriver, DispatchQueue, QueueTrip,
  MapDriver, DispatchStats, TripCreatePayload, DispatchDriverStatus,
} from '../types'
import { Phone, MapPin, Car, Clock, AlertTriangle, Check, X, RefreshCw, Plus } from 'lucide-react'
import clsx from 'clsx'
import { format, parseISO } from 'date-fns'

// ── Constants ─────────────────────────────────────────────────────────────

type City = 'saskatoon' | 'regina'
type QueueTab = 'dispatch' | 'pre_booked' | 'booked' | 'in_progress' | 'completed' | 'cancelled' | 'noshow'

const TAB_LABELS: Record<QueueTab, string> = {
  dispatch:    'DISPATCH',
  pre_booked:  'PRE-BOOKED',
  booked:      'BOOKED',
  in_progress: 'IN PROGRESS',
  completed:   'COMPLETED',
  cancelled:   'CANCELLED',
  noshow:      'NO SHOW',
}

const PRIORITY_LABELS = ['Normal', 'High', 'Urgent']
const PRIORITY_COLORS = ['text-gray-400', 'text-amber-400', 'text-red-400']

const DRIVER_STATUS_COLOR: Record<DispatchDriverStatus, string> = {
  online:   'bg-emerald-500',
  parked:   'bg-cyan-500',
  dropping: 'bg-blue-500',
  bidding:  'bg-purple-500',
  on_trip:  'bg-amber-500',
  break:    'bg-gray-500',
  offline:  'bg-gray-700',
}

// Saskatoon city center bounds for simple coordinate → pixel mapping
const MAP_BOUNDS = {
  saskatoon: { minLat: 52.08, maxLat: 52.20, minLng: -106.76, maxLng: -106.57 },
  regina:    { minLat: 50.38, maxLat: 50.48, minLng: -104.68, maxLng: -104.56 },
}

// ── Map component ──────────────────────────────────────────────────────────

function DispatchMap({ drivers, city }: { drivers: MapDriver[]; city: City }) {
  const bounds = MAP_BOUNDS[city]
  const toPercent = (lat: number, lng: number) => ({
    x: ((lng - bounds.minLng) / (bounds.maxLng - bounds.minLng)) * 100,
    y: (1 - (lat - bounds.minLat) / (bounds.maxLat - bounds.minLat)) * 100,
  })

  return (
    <div className="relative w-full h-full bg-gray-900 rounded-lg overflow-hidden border border-gray-700">
      {/* Grid lines */}
      <svg className="absolute inset-0 w-full h-full opacity-10" xmlns="http://www.w3.org/2000/svg">
        {[1,2,3,4].map(i => (
          <line key={`v${i}`} x1={`${i*20}%`} y1="0" x2={`${i*20}%`} y2="100%"
            stroke="#6b7280" strokeWidth="1" />
        ))}
        {[1,2,3,4].map(i => (
          <line key={`h${i}`} x1="0" y1={`${i*20}%`} x2="100%" y2={`${i*20}%`}
            stroke="#6b7280" strokeWidth="1" />
        ))}
      </svg>

      {/* City label */}
      <div className="absolute top-2 left-2 text-xs text-gray-500 uppercase tracking-widest font-mono">
        {city} · live map
      </div>

      {/* Driver markers */}
      {drivers.filter(d => d.lat && d.lng).map(d => {
        const pos = toPercent(d.lat!, d.lng!)
        if (pos.x < 0 || pos.x > 100 || pos.y < 0 || pos.y > 100) return null
        return (
          <div
            key={d.driver_id}
            className="absolute transform -translate-x-1/2 -translate-y-1/2 group"
            style={{ left: `${pos.x}%`, top: `${pos.y}%` }}
          >
            <div className={clsx(
              'w-4 h-4 rounded-full border-2 border-gray-900 cursor-pointer transition-transform hover:scale-125',
              DRIVER_STATUS_COLOR[d.status]
            )} />
            <div className="hidden group-hover:block absolute bottom-5 left-1/2 -translate-x-1/2 z-10
              bg-gray-800 border border-gray-600 rounded px-2 py-1 text-xs whitespace-nowrap shadow-lg">
              <p className="font-semibold text-white">{d.name}</p>
              <p className="text-gray-400">{d.vehicle_plate} · {d.status}</p>
            </div>
          </div>
        )
      })}

      {/* No drivers fallback */}
      {drivers.filter(d => d.lat && d.lng).length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="text-center text-gray-600">
            <MapPin size={24} className="mx-auto mb-1" />
            <p className="text-xs">No drivers with GPS data</p>
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="absolute bottom-2 right-2 flex flex-col gap-1">
        {(['online','parked','dropping','bidding','on_trip'] as DispatchDriverStatus[]).map(s => (
          <div key={s} className="flex items-center gap-1">
            <div className={clsx('w-2.5 h-2.5 rounded-full', DRIVER_STATUS_COLOR[s])} />
            <span className="text-xs text-gray-500 capitalize">{s}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Booking form ──────────────────────────────────────────────────────────

const EMPTY_FORM: TripCreatePayload = {
  customer_phone: '',
  customer_name: '',
  customer_email: '',
  pickup_address: '',
  dropoff_address: '',
  via_address: '',
  city: 'saskatoon',
  notes: '',
  instructions: '',
  site: '',
  priority: 0,
  booking_source: 'agent',
}

function BookingForm({
  city,
  onBooked,
}: {
  city: City
  onBooked: (trip: DispatchTrip) => void
}) {
  const [form, setForm] = useState<TripCreatePayload>({ ...EMPTY_FORM, city })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [scheduledFor, setScheduledFor] = useState('')

  useEffect(() => {
    setForm(f => ({ ...f, city }))
  }, [city])

  const set = (k: keyof TripCreatePayload, v: unknown) =>
    setForm(f => ({ ...f, [k]: v }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    if (!form.customer_phone || !form.pickup_address || !form.dropoff_address) {
      setError('Phone, pickup and destination are required.')
      return
    }
    setSaving(true)
    try {
      const payload: TripCreatePayload = { ...form }
      if (scheduledFor) payload.scheduled_for = new Date(scheduledFor).toISOString()
      const trip = await api.createTrip(payload)
      onBooked(trip)
      setForm({ ...EMPTY_FORM, city })
      setScheduledFor('')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create booking')
    } finally {
      setSaving(false)
    }
  }

  const inputCls = 'w-full bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm text-gray-200 focus:outline-none focus:border-amber-500 placeholder-gray-600'
  const labelCls = 'text-xs text-gray-500 uppercase tracking-wide w-14 flex-shrink-0'

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2 text-sm">
      {/* Phone */}
      <div className="flex items-center gap-2">
        <span className={labelCls}>PH</span>
        <input className={inputCls} placeholder="+1 306 …" value={form.customer_phone}
          onChange={e => set('customer_phone', e.target.value)} />
      </div>
      {/* Name */}
      <div className="flex items-center gap-2">
        <span className={labelCls}>NAME</span>
        <input className={inputCls} placeholder="Customer name" value={form.customer_name ?? ''}
          onChange={e => set('customer_name', e.target.value)} />
      </div>
      {/* Email */}
      <div className="flex items-center gap-2">
        <span className={labelCls}>EMAIL</span>
        <input className={inputCls} type="email" placeholder="customer@email.com" value={form.customer_email ?? ''}
          onChange={e => set('customer_email', e.target.value)} />
      </div>
      {/* Pickup */}
      <div className="flex items-center gap-2">
        <span className={labelCls}>ADDR</span>
        <input className={inputCls} placeholder="Pickup address [F2]" value={form.pickup_address}
          onChange={e => set('pickup_address', e.target.value)} />
      </div>
      {/* Destination */}
      <div className="flex items-center gap-2">
        <span className={labelCls}>DEST</span>
        <input className={inputCls} placeholder="Destination [F2]" value={form.dropoff_address}
          onChange={e => set('dropoff_address', e.target.value)} />
      </div>
      {/* Via */}
      <div className="flex items-center gap-2">
        <span className={labelCls}>VIA</span>
        <input className={inputCls} placeholder="Via (intermediate stop)" value={form.via_address ?? ''}
          onChange={e => set('via_address', e.target.value)} />
      </div>
      {/* Instructions */}
      <div className="flex items-center gap-2">
        <span className={labelCls}>INST</span>
        <input className={inputCls} placeholder="Special instructions" value={form.instructions ?? ''}
          onChange={e => set('instructions', e.target.value)} />
      </div>
      {/* Site */}
      <div className="flex items-center gap-2">
        <span className={labelCls}>SITE</span>
        <input className={inputCls} placeholder="Site / account" value={form.site ?? ''}
          onChange={e => set('site', e.target.value)} />
      </div>
      {/* Scheduled for */}
      <div className="flex items-center gap-2">
        <span className={labelCls}>TIME</span>
        <input className={inputCls} type="datetime-local" value={scheduledFor}
          onChange={e => setScheduledFor(e.target.value)} />
      </div>
      {/* Priority */}
      <div className="flex items-center gap-2">
        <span className={labelCls}>PPL</span>
        <div className="flex gap-1">
          {PRIORITY_LABELS.map((label, i) => (
            <button
              key={i}
              type="button"
              onClick={() => set('priority', i)}
              className={clsx(
                'px-2 py-0.5 rounded text-xs border transition-colors',
                form.priority === i
                  ? 'bg-amber-500 border-amber-500 text-gray-950 font-semibold'
                  : 'bg-gray-800 border-gray-700 text-gray-400 hover:text-gray-200'
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <p className="text-xs text-red-400 mt-1">{error}</p>
      )}

      <button
        type="submit"
        disabled={saving}
        className="mt-2 w-full bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-gray-950 font-semibold py-2 rounded text-sm transition-colors"
      >
        {saving ? 'Saving…' : 'Save Job [F1]'}
      </button>
    </form>
  )
}

// ── Driver status pane ────────────────────────────────────────────────────

function DriverStatusPane({ drivers }: { drivers: DispatchDriver[] }) {
  const groups: { label: string; statuses: DispatchDriverStatus[]; color: string }[] = [
    { label: 'Parked', statuses: ['parked', 'online'], color: 'text-cyan-400' },
    { label: 'Dropping', statuses: ['dropping'], color: 'text-blue-400' },
    { label: 'Bidding', statuses: ['bidding'], color: 'text-purple-400' },
    { label: 'On Trip', statuses: ['on_trip'], color: 'text-amber-400' },
    { label: 'Break', statuses: ['break'], color: 'text-gray-400' },
  ]

  return (
    <div className="flex flex-col gap-3 overflow-y-auto">
      {groups.map(({ label, statuses, color }) => {
        const group = drivers.filter(d => statuses.includes(d.status))
        return (
          <div key={label}>
            <div className="flex items-center gap-2 mb-1">
              <span className={clsx('text-xs font-semibold uppercase tracking-wide', color)}>
                {label}
              </span>
              <span className="text-xs text-gray-600">({group.length})</span>
            </div>
            {group.length === 0 ? (
              <p className="text-xs text-gray-700 pl-2">—</p>
            ) : (
              <div className="flex flex-col gap-1">
                {group.map(d => (
                  <div key={d.id} className="flex items-center gap-2 px-2 py-1 rounded bg-gray-800/50 hover:bg-gray-800 transition-colors">
                    <div className={clsx('w-2 h-2 rounded-full flex-shrink-0', DRIVER_STATUS_COLOR[d.status])} />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-gray-200 truncate font-medium">{d.name}</p>
                      <p className="text-xs text-gray-600">{d.vehicle_plate || '—'}</p>
                    </div>
                    <span className="text-xs text-gray-600">★{d.rating.toFixed(1)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── Job board table ───────────────────────────────────────────────────────

function formatTime(iso?: string | null): string {
  if (!iso) return '—'
  try { return format(parseISO(iso), 'HH:mm') } catch { return '—' }
}

function JobRow({
  trip,
  onCancel,
  onNoShow,
}: {
  trip: QueueTrip
  onCancel: (id: string) => void
  onNoShow: (id: string) => void
}) {
  const priorityColor = PRIORITY_COLORS[trip.priority ?? 0]
  const isActive = ['pending', 'assigned', 'en_route', 'arrived', 'in_progress'].includes(trip.status)

  return (
    <tr className="border-b border-gray-800 hover:bg-gray-800/40 transition-colors">
      <td className="px-2 py-1.5 text-xs text-gray-400 font-mono whitespace-nowrap">
        {formatTime(trip.requested_at)}
      </td>
      <td className="px-2 py-1.5">
        <span className={clsx('text-xs font-bold', priorityColor)}>
          {PRIORITY_LABELS[trip.priority ?? 0][0]}
        </span>
      </td>
      <td className="px-2 py-1.5 text-xs text-gray-300 max-w-[140px] truncate">
        {trip.pickup_address}
      </td>
      <td className="px-2 py-1.5 text-xs text-gray-400 max-w-[140px] truncate">
        {trip.dropoff_address}
      </td>
      <td className="px-2 py-1.5 text-xs text-gray-300 max-w-[100px] truncate">
        {trip.customer_name || '—'}
      </td>
      <td className="px-2 py-1.5 text-xs text-gray-400 font-mono whitespace-nowrap">
        {trip.customer_phone}
      </td>
      <td className="px-2 py-1.5 text-xs text-gray-500">
        {trip.driver_id ? trip.driver_id.slice(0, 6) : '—'}
      </td>
      <td className="px-2 py-1.5 text-xs">
        <span className={clsx('px-1.5 py-0.5 rounded text-xs font-medium', {
          'bg-amber-500/15 text-amber-400': trip.status === 'pending',
          'bg-blue-500/15 text-blue-400':   ['assigned','en_route','arrived'].includes(trip.status),
          'bg-emerald-500/15 text-emerald-400': trip.status === 'completed' || trip.status === 'in_progress',
          'bg-red-500/15 text-red-400':     trip.status === 'cancelled',
          'bg-gray-500/15 text-gray-400':   trip.status === 'noshow',
        })}>
          {trip.status.replace('_', ' ')}
        </span>
      </td>
      {isActive && (
        <td className="px-2 py-1.5">
          <div className="flex gap-1">
            <button
              onClick={() => onNoShow(trip.trip_id)}
              title="No Show"
              className="p-1 rounded text-gray-600 hover:text-amber-400 hover:bg-gray-700 transition-colors"
            >
              <AlertTriangle size={12} />
            </button>
            <button
              onClick={() => onCancel(trip.trip_id)}
              title="Cancel"
              className="p-1 rounded text-gray-600 hover:text-red-400 hover:bg-gray-700 transition-colors"
            >
              <X size={12} />
            </button>
          </div>
        </td>
      )}
      {!isActive && <td />}
    </tr>
  )
}

function JobBoard({
  queue,
  activeTab,
  onTabChange,
  onCancel,
  onNoShow,
  search,
  onSearchChange,
}: {
  queue: DispatchQueue | null
  activeTab: QueueTab
  onTabChange: (t: QueueTab) => void
  onCancel: (id: string) => void
  onNoShow: (id: string) => void
  search: string
  onSearchChange: (v: string) => void
}) {
  const rows = queue ? queue[activeTab] : []
  const filtered = search
    ? rows.filter(t =>
        t.pickup_address.toLowerCase().includes(search.toLowerCase()) ||
        t.customer_name.toLowerCase().includes(search.toLowerCase()) ||
        t.customer_phone.includes(search)
      )
    : rows

  return (
    <div className="flex flex-col min-h-0">
      {/* Tabs */}
      <div className="flex items-center gap-0.5 border-b border-gray-700 overflow-x-auto">
        {(Object.keys(TAB_LABELS) as QueueTab[]).map(tab => {
          const count = queue ? queue[tab].length : 0
          return (
            <button
              key={tab}
              onClick={() => onTabChange(tab)}
              className={clsx(
                'px-3 py-2 text-xs font-medium whitespace-nowrap transition-colors border-b-2 -mb-px',
                activeTab === tab
                  ? 'border-amber-500 text-amber-400'
                  : 'border-transparent text-gray-500 hover:text-gray-300'
              )}
            >
              {TAB_LABELS[tab]}{' '}
              <span className={clsx(
                'ml-1 px-1.5 py-0.5 rounded-full text-xs',
                count > 0 && activeTab === tab ? 'bg-amber-500 text-gray-950' : 'bg-gray-700 text-gray-400'
              )}>
                {count}
              </span>
            </button>
          )
        })}
        {/* Search */}
        <div className="ml-auto px-2">
          <input
            className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-gray-300 placeholder-gray-600 focus:outline-none focus:border-amber-500 w-40"
            placeholder="Search bookings…"
            value={search}
            onChange={e => onSearchChange(e.target.value)}
          />
        </div>
      </div>

      {/* Table */}
      <div className="overflow-auto flex-1">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-gray-700">
              {['Time','P','Pickup','Destination','Name','Phone','Driver','Status',''].map(h => (
                <th key={h} className="px-2 py-1.5 text-xs text-gray-600 font-medium whitespace-nowrap">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-4 py-8 text-center text-gray-600 text-sm">
                  No jobs in this queue
                </td>
              </tr>
            ) : (
              filtered.map(t => (
                <JobRow key={t.trip_id} trip={t} onCancel={onCancel} onNoShow={onNoShow} />
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Main Dispatch page ────────────────────────────────────────────────────

export default function Dispatch() {
  const [city, setCity] = useState<City>('saskatoon')
  const [activeTab, setActiveTab] = useState<QueueTab>('dispatch')
  const [search, setSearch] = useState('')
  const [lastBooked, setLastBooked] = useState<DispatchTrip | null>(null)

  // Data
  const { data: queue, reload: refreshQueue } = useApi(
    () => api.getDispatchQueue(city, 4),
    [city],
    { interval: 8_000 }
  )
  const { data: mapData } = useApi(
    () => api.getDispatchMap(city),
    [city],
    { interval: 10_000 }
  )
  const { data: stats } = useApi(
    () => api.getDispatchStats(city),
    [city],
    { interval: 20_000 }
  )
  const { data: dispatchDrivers } = useApi(
    () => api.listDispatchDrivers({ city }),
    [city],
    { interval: 10_000 }
  )

  // WebSocket for real-time updates
  const wsRef = useRef<WebSocket | null>(null)
  useEffect(() => {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${proto}://${window.location.host}/dispatch/dashboard/ws`)
    wsRef.current = ws
    ws.onmessage = () => {
      refreshQueue()
    }
    ws.onerror = () => {}  // silently ignore if unavailable
    return () => { ws.close() }
  }, [refreshQueue])

  const handleBooked = useCallback((trip: DispatchTrip) => {
    setLastBooked(trip)
    refreshQueue()
    setTimeout(() => setLastBooked(null), 5000)
  }, [refreshQueue])

  const handleCancel = async (id: string) => {
    if (!window.confirm('Cancel this trip?')) return
    try {
      await api.cancelTrip(id, 'Cancelled by dispatcher')
      refreshQueue()
    } catch {}
  }

  const handleNoShow = async (id: string) => {
    if (!window.confirm('Mark as no-show?')) return
    try {
      await api.noShowTrip(id)
      refreshQueue()
    } catch {}
  }

  const activeDrivers = dispatchDrivers?.filter(d => d.status !== 'offline') ?? []
  const pendingCount = queue?.dispatch.length ?? 0
  const completedCount = queue?.completed.length ?? 0

  return (
    <div className="flex flex-col h-full gap-3" style={{ minHeight: 0 }}>

      {/* ── City selector + stats bar ──────────────────────────────────── */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex gap-1">
          {(['saskatoon', 'regina'] as City[]).map(c => (
            <button
              key={c}
              onClick={() => setCity(c)}
              className={clsx(
                'px-4 py-1.5 rounded text-xs font-semibold uppercase tracking-wide transition-colors',
                city === c
                  ? 'bg-amber-500 text-gray-950'
                  : 'bg-gray-800 text-gray-400 hover:text-gray-200'
              )}
            >
              {c}
            </button>
          ))}
        </div>

        <div className="flex gap-3 text-xs ml-2">
          <span className="text-gray-500">
            Drivers online:{' '}
            <span className="text-emerald-400 font-semibold">{activeDrivers.length}</span>
          </span>
          <span className="text-gray-500">
            Pending:{' '}
            <span className="text-amber-400 font-semibold">{pendingCount}</span>
          </span>
          <span className="text-gray-500">
            Completed (4h):{' '}
            <span className="text-gray-300 font-semibold">{completedCount}</span>
          </span>
          {stats?.avg_wait_minutes != null && (
            <span className="text-gray-500">
              Avg wait:{' '}
              <span className="text-gray-300 font-semibold">{stats.avg_wait_minutes}m</span>
            </span>
          )}
        </div>

        <button
          onClick={refreshQueue}
          className="ml-auto p-1.5 rounded text-gray-600 hover:text-gray-300 hover:bg-gray-800 transition-colors"
          title="Refresh"
        >
          <RefreshCw size={14} />
        </button>
      </div>

      {/* ── Booking confirmed flash ────────────────────────────────────── */}
      {lastBooked && (
        <div className="flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/30 rounded px-3 py-2 text-xs text-emerald-400">
          <Check size={14} />
          <span>Job saved — ID {lastBooked.id.slice(0, 8)}… | {lastBooked.pickup_address} → {lastBooked.dropoff_address}</span>
        </div>
      )}

      {/* ── Main 3-column layout ───────────────────────────────────────── */}
      <div className="grid grid-cols-[280px_220px_1fr] gap-3 flex-1 min-h-0" style={{ height: '340px' }}>

        {/* Col 1: Booking form */}
        <div className="card overflow-y-auto">
          <div className="flex items-center gap-2 mb-3">
            <Plus size={14} className="text-amber-400" />
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide">New Booking</h3>
          </div>
          <BookingForm city={city} onBooked={handleBooked} />
        </div>

        {/* Col 2: Driver status pane */}
        <div className="card overflow-hidden flex flex-col">
          <div className="flex items-center gap-2 mb-3">
            <Car size={14} className="text-amber-400" />
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Driver Status</h3>
          </div>
          {dispatchDrivers ? (
            <DriverStatusPane drivers={dispatchDrivers} />
          ) : (
            <div className="flex-1 flex items-center justify-center text-gray-600 text-xs">
              Loading drivers…
            </div>
          )}
        </div>

        {/* Col 3: Live map */}
        <div className="card overflow-hidden p-0">
          <DispatchMap
            drivers={mapData?.drivers ?? []}
            city={city}
          />
        </div>
      </div>

      {/* ── Job board ──────────────────────────────────────────────────── */}
      <div className="card flex-1 flex flex-col min-h-0 overflow-hidden" style={{ minHeight: '300px' }}>
        <JobBoard
          queue={queue ?? null}
          activeTab={activeTab}
          onTabChange={setActiveTab}
          onCancel={handleCancel}
          onNoShow={handleNoShow}
          search={search}
          onSearchChange={setSearch}
        />
      </div>

    </div>
  )
}
