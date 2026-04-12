import { useParams, useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { useApi } from '../hooks/useApi'
import { api } from '../lib/api'
import { ArrowLeft, Save, AlertOctagon, MessageSquare, CheckCircle, Clock, UserX, UserCheck, FileText, Send } from 'lucide-react'
import clsx from 'clsx'
import { format } from 'date-fns'
import type { Driver, DriverDocument, ActivityLog } from '../types'

// ── Reusable layout helpers ──────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="overflow-hidden rounded-lg border border-gray-700">
      <div className="bg-gray-800 px-4 py-2.5 border-b border-gray-700">
        <h3 className="text-xs font-semibold text-gray-400 tracking-widest uppercase">{title}</h3>
      </div>
      <div className="bg-gray-900/60 p-4 space-y-2.5">{children}</div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid items-center gap-3" style={{ gridTemplateColumns: '148px 1fr' }}>
      <label className="text-xs text-gray-400 tracking-wide text-right">{label}</label>
      <div>{children}</div>
    </div>
  )
}

// ── Document upload slot ─────────────────────────────────────────────────────

const DOC_STATUS_CLS: Record<string, string> = {
  valid:         'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20',
  expiring:      'bg-amber-500/10  text-amber-400  border border-amber-500/20',
  expiring_soon: 'bg-orange-500/10 text-orange-400 border border-orange-500/20',
  expired:       'bg-red-500/10    text-red-400    border border-red-500/20',
}

function DocSlot({ label, doc }: { label: string; doc?: DriverDocument }) {
  return (
    <div className="p-4 border-gray-700 bg-gray-900/60">
      <p className="text-xs font-semibold text-gray-400 tracking-widest uppercase mb-3">{label}</p>
      {doc ? (
        <div className="flex items-center justify-between gap-2">
          <span className={clsx('badge text-xs capitalize', DOC_STATUS_CLS[doc.status] ?? 'bg-gray-700 text-gray-400')}>
            {doc.status.replace('_', ' ')}
          </span>
          {doc.expiry_date && (
            <span className="text-xs text-gray-500">
              {format(new Date(doc.expiry_date), 'MMM d, yyyy')}
            </span>
          )}
        </div>
      ) : (
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-600">NO FILE</span>
          <button className="text-xs px-2 py-1 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded transition-colors tracking-wide">
            UPLOAD
          </button>
        </div>
      )}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

type FormState = Omit<Driver, 'id' | 'total_trips' | 'total_earnings' | 'documents' | 'created_at' | 'performance_score'>

const DAYS = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']

const DOC_SLOTS = [
  { key: 'police_disclosure', label: 'POLICE DISCLOSURE' },
  { key: 'agreement',         label: 'AGREEMENT'         },
  { key: 'proof_of_address',  label: 'PROOF OF ADDRESS'  },
  { key: 'photo_id',          label: 'PHOTO ID'          },
  { key: 'licence_photo',     label: 'LICENCE PHOTO'     },
  { key: 'insurance',         label: 'INSURANCE'         },
]

export default function DriverProfile() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [message, setMessage]     = useState('')
  const [msgSent, setMsgSent]     = useState(false)
  const [hrType, setHrType]       = useState('warning_letter')
  const [hrDraft, setHrDraft]     = useState('')
  const [hrLoading, setHrLoading] = useState(false)
  const [saveLoading, setSaveLoading] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)

  // Suspend modal
  const [suspendModal, setSuspendModal]   = useState(false)
  const [suspendReason, setSuspendReason] = useState('')
  const [suspendLoading, setSuspendLoading] = useState(false)

  const { data: driver, loading, reload } = useApi(() => api.getDriver(id!), [id])
  const { data: trips } = useApi(() => api.driverTrips(id!), [id])
  const { data: activityLog, reload: reloadLog } = useApi(() => api.driverActivityLog(id!), [id])

  const [form, setForm] = useState<FormState>({
    name: '', phone: '', email: '', city: 'saskatoon', status: 'active',
    commission_rate: 0.3, vehicle_plate: '', vehicle_model: '',
    // personal
    first_name: '', last_name: '', aka: '', address: '',
    mobile_phone: '', other_phone: '', sex: 'male',
    // professional
    driver_type: 'regular',
    // licensing
    badge_number: '', badge_expiry: '', badge_type: 'hackney',
    licence_number: '', licence_expiry: '', tax_number: '',
    // attributes
    accept_discount: true, accept_account: true,
    accept_cash_work: true, accept_fixed_fares: true,
    // device
    device_imei: '',
    // payments
    payment_on: 'sunday', payment_type: 'cash',
    bank_name: '', bank_account_number: '', sort_code: '',
    // sites
    primary_site: 'saskatoon',
    notes: '',
  })

  useEffect(() => {
    if (!driver) return
    setForm({
      name:               driver.name           ?? '',
      phone:              driver.phone          ?? '',
      email:              driver.email          ?? '',
      city:               driver.city           ?? 'saskatoon',
      status:             driver.status         ?? 'active',
      commission_rate:    driver.commission_rate ?? 0.3,
      vehicle_plate:      driver.vehicle_plate  ?? '',
      vehicle_model:      driver.vehicle_model  ?? '',
      first_name:         driver.first_name     ?? '',
      last_name:          driver.last_name      ?? '',
      aka:                driver.aka            ?? '',
      address:            driver.address        ?? '',
      mobile_phone:       driver.mobile_phone   ?? '',
      other_phone:        driver.other_phone    ?? '',
      sex:                driver.sex            ?? 'male',
      driver_type:        driver.driver_type    ?? 'regular',
      badge_number:       driver.badge_number   ?? '',
      badge_expiry:       driver.badge_expiry   ?? '',
      badge_type:         driver.badge_type     ?? 'hackney',
      licence_number:     driver.licence_number ?? '',
      licence_expiry:     driver.licence_expiry ?? '',
      tax_number:         driver.tax_number     ?? '',
      accept_discount:    driver.accept_discount    ?? true,
      accept_account:     driver.accept_account     ?? true,
      accept_cash_work:   driver.accept_cash_work   ?? true,
      accept_fixed_fares: driver.accept_fixed_fares ?? true,
      device_imei:        driver.device_imei    ?? '',
      payment_on:         driver.payment_on     ?? 'sunday',
      payment_type:       driver.payment_type   ?? 'cash',
      bank_name:          driver.bank_name      ?? '',
      bank_account_number: driver.bank_account_number ?? '',
      sort_code:          driver.sort_code      ?? '',
      primary_site:       driver.primary_site   ?? 'saskatoon',
      notes:              driver.notes          ?? '',
    })
  }, [driver])

  // Helpers
  const set = (key: keyof FormState, val: unknown) => setForm(f => ({ ...f, [key]: val }))

  const inp = (key: keyof FormState) => ({
    className: 'input w-full text-sm',
    value: (form[key] ?? '') as string,
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => set(key, e.target.value),
  })

  const sel = (key: keyof FormState) => ({
    className: 'input w-full text-sm',
    value: (form[key] ?? '') as string,
    onChange: (e: React.ChangeEvent<HTMLSelectElement>) => set(key, e.target.value),
  })

  const handleSave = async () => {
    setSaveLoading(true)
    setSaveSuccess(false)
    try {
      await api.updateDriver(id!, form as Parameters<typeof api.updateDriver>[1])
      setSaveSuccess(true)
      reload()
      reloadLog()
      setTimeout(() => setSaveSuccess(false), 3000)
    } finally {
      setSaveLoading(false)
    }
  }

  const handleSuspendConfirm = async () => {
    if (!suspendReason.trim()) return
    setSuspendLoading(true)
    try {
      await api.suspendDriver(id!, suspendReason)
      setSuspendModal(false)
      setSuspendReason('')
      reload()
      reloadLog()
    } finally {
      setSuspendLoading(false)
    }
  }

  const handleActivate = async () => {
    await api.activateDriver(id!)
    reload()
    reloadLog()
  }

  const handleMessage = async () => {
    if (!message.trim()) return
    await api.messageDriver(id!, message)
    setMessage('')
    setMsgSent(true)
    reloadLog()
    setTimeout(() => setMsgSent(false), 3000)
  }

  const handleDraftHR = async () => {
    setHrLoading(true)
    setHrDraft('')
    try {
      const result: any = await api.draftHRDocument(hrType, id!)
      setHrDraft(result.content)
    } finally {
      setHrLoading(false)
    }
  }

  if (loading) return (
    <div className="space-y-4">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="h-24 bg-gray-800 rounded animate-pulse" />
      ))}
    </div>
  )

  if (!driver) return (
    <div className="card text-center py-16 text-gray-600">Driver not found</div>
  )

  return (
    <div className="space-y-4 max-w-6xl">

      {/* ── Header ── */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <button onClick={() => navigate('/drivers')} className="flex items-center gap-1.5 hover:text-white transition-colors">
            <ArrowLeft size={13} /> Drivers
          </button>
          <span className="text-gray-600">&gt;&gt;</span>
          <span className="text-white font-semibold tracking-wide">{driver.name}</span>
        </div>
        <div className="flex items-center gap-2">
          {saveSuccess && (
            <span className="text-xs text-emerald-400 flex items-center gap-1">
              <CheckCircle size={12} /> Saved
            </span>
          )}
          {driver.status === 'suspended'
            ? <button onClick={handleActivate} className="btn-success text-xs px-4 tracking-widest">ACTIVATE</button>
            : <button onClick={() => setSuspendModal(true)} className="btn-danger text-xs px-4 tracking-widest">SUSPEND</button>
          }
          <button
            onClick={handleSave}
            disabled={saveLoading}
            className="btn-primary flex items-center gap-2 text-xs px-5 tracking-widest"
          >
            <Save size={13} />
            {saveLoading ? 'SAVING...' : 'SAVE'}
          </button>
        </div>
      </div>

      {/* ── Row 1: Details | Personal ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        <Section title="Details">
          <Field label="DRIVER ID / LOGIN">
            <input
              className="input w-full text-sm text-gray-500 cursor-not-allowed"
              value={driver.id.slice(0, 8).toUpperCase()}
              readOnly
            />
          </Field>
          <Field label="PHONE">
            <input {...inp('phone')} />
          </Field>
          <Field label="VEHICLE">
            <div className="flex gap-2">
              <input
                className="input flex-1 text-sm"
                placeholder="Model"
                value={form.vehicle_model ?? ''}
                onChange={e => set('vehicle_model', e.target.value)}
              />
              <input
                className="input w-28 text-sm uppercase"
                placeholder="PLATE"
                value={form.vehicle_plate ?? ''}
                onChange={e => set('vehicle_plate', e.target.value)}
              />
            </div>
          </Field>
          <Field label="STATUS">
            <select {...sel('status')}>
              <option value="active">ACTIVE</option>
              <option value="offline">INACTIVE</option>
              <option value="on_trip">ON TRIP</option>
              <option value="suspended">SUSPENDED</option>
              <option value="pending">PENDING / ONBOARDING</option>
            </select>
          </Field>
          <Field label="DRIVER TYPE">
            <select {...sel('driver_type')}>
              <option value="regular">Regular Driver</option>
              <option value="wheelchair">Wheelchair</option>
              <option value="executive">Executive</option>
              <option value="school">School</option>
            </select>
          </Field>
        </Section>

        <Section title="Personal">
          <Field label="FIRST NAME">
            <input {...inp('first_name')} />
          </Field>
          <Field label="LAST NAME">
            <input {...inp('last_name')} />
          </Field>
          <Field label="A.K.A.">
            <input {...inp('aka')} />
          </Field>
          <Field label="ADDRESS">
            <input {...inp('address')} />
          </Field>
          <Field label="EMAIL">
            <input {...inp('email')} type="email" />
          </Field>
          <Field label="MOBILE PHONE">
            <input {...inp('mobile_phone')} />
          </Field>
          <Field label="OTHER PHONE">
            <input {...inp('other_phone')} />
          </Field>
          <Field label="SEX">
            <select {...sel('sex')}>
              <option value="male">Male</option>
              <option value="female">Female</option>
              <option value="other">Other / Prefer not to say</option>
            </select>
          </Field>
        </Section>
      </div>

      {/* ── Row 2: Licensing | Attributes ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        <Section title="Licensing">
          <Field label="START DATE">
            <input
              className="input w-full text-sm text-gray-500 cursor-not-allowed"
              value={driver.created_at ? driver.created_at.slice(0, 10) : '—'}
              readOnly
            />
          </Field>
          <Field label="BADGE">
            <input {...inp('badge_number')} placeholder="Badge / PSV number" />
          </Field>
          <Field label="BADGE EXPIRY">
            <input {...inp('badge_expiry')} type="date" />
          </Field>
          <Field label="BADGE TYPE">
            <select {...sel('badge_type')}>
              <option value="hackney">Hackney</option>
              <option value="metropolitan">Metropolitan</option>
              <option value="provincial">Provincial</option>
            </select>
          </Field>
          <Field label="LICENCE">
            <input {...inp('licence_number')} placeholder="Driver's licence number" />
          </Field>
          <Field label="LICENCE EXPIRY">
            <input {...inp('licence_expiry')} type="date" />
          </Field>
          <Field label="TAX NUMBER">
            <input {...inp('tax_number')} />
          </Field>
        </Section>

        <Section title="Attributes">
          {([
            ['ACCEPT DISCOUNT',    'accept_discount'   ],
            ['ACCEPT ACCOUNT',     'accept_account'    ],
            ['ACCEPT CASH WORK',   'accept_cash_work'  ],
            ['ACCEPT FIXED FARES', 'accept_fixed_fares'],
          ] as const).map(([label, key]) => (
            <Field key={key} label={label}>
              <select
                className="input w-full text-sm"
                value={(form[key] ?? true) ? 'yes' : 'no'}
                onChange={e => set(key, e.target.value === 'yes')}
              >
                <option value="yes">YES</option>
                <option value="no">NO</option>
              </select>
            </Field>
          ))}
          <Field label="PERFORMANCE">
            <input
              className="input w-full text-sm text-gray-500 cursor-not-allowed"
              value={`${driver.performance_score?.toFixed(0) ?? 0} / 100`}
              readOnly
            />
          </Field>
          <Field label="TOTAL TRIPS">
            <input
              className="input w-full text-sm text-gray-500 cursor-not-allowed"
              value={driver.total_trips ?? 0}
              readOnly
            />
          </Field>
          <Field label="TOTAL EARNINGS">
            <input
              className="input w-full text-sm text-gray-500 cursor-not-allowed"
              value={`$${(driver.total_earnings ?? 0).toLocaleString('en-CA', { minimumFractionDigits: 2 })}`}
              readOnly
            />
          </Field>
        </Section>
      </div>

      {/* ── Row 3: Notes | Device ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        <Section title="Notes">
          <div className="grid items-start gap-3" style={{ gridTemplateColumns: '148px 1fr' }}>
            <label className="text-xs text-gray-400 tracking-wide text-right pt-2">NOTES</label>
            <textarea
              className="input h-28 resize-none text-sm w-full"
              placeholder="Driver notes..."
              value={form.notes ?? ''}
              onChange={e => set('notes', e.target.value)}
            />
          </div>
        </Section>

        <Section title="Device">
          <Field label="DEVICE IMEI / UID">
            <input {...inp('device_imei')} placeholder="IMEI or device UID" />
          </Field>
        </Section>
      </div>

      {/* ── Row 4: Invoicing | Payments ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        <Section title="Invoicing / Shifts">
          <Field label="COMMISSION (%)">
            <input
              className="input w-full text-sm"
              type="number"
              min="0"
              max="100"
              value={Math.round((form.commission_rate ?? 0.3) * 100)}
              onChange={e => set('commission_rate', Number(e.target.value) / 100)}
            />
          </Field>
          <Field label="PAYMENT ON">
            <select {...sel('payment_on')}>
              {DAYS.map(d => (
                <option key={d} value={d}>{d.charAt(0).toUpperCase() + d.slice(1)}</option>
              ))}
            </select>
          </Field>
        </Section>

        <Section title="Payments">
          <Field label="PAYMENT TYPE">
            <select {...sel('payment_type')}>
              <option value="cash">Cash</option>
              <option value="bank_transfer">Bank Transfer</option>
              <option value="card">Card</option>
            </select>
          </Field>
          <Field label="BANK NAME">
            <input {...inp('bank_name')} />
          </Field>
          <Field label="ACCOUNT NUMBER">
            <input {...inp('bank_account_number')} />
          </Field>
          <Field label="SORT CODE">
            <input {...inp('sort_code')} />
          </Field>
        </Section>
      </div>

      {/* ── Documents ── */}
      <div className="overflow-hidden rounded-lg border border-gray-700">
        <div className="bg-gray-800 px-4 py-2.5 border-b border-gray-700">
          <h3 className="text-xs font-semibold text-gray-400 tracking-widest uppercase">Documents</h3>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 divide-x divide-y divide-gray-700">
          {DOC_SLOTS.map(({ key, label }) => {
            const existing = driver.documents?.find(d => d.type === key)
            return <DocSlot key={key} label={label} doc={existing} />
          })}
        </div>
      </div>

      {/* ── Site Assignment ── */}
      <div className="overflow-hidden rounded-lg border border-gray-700">
        <div className="bg-gray-800 px-4 py-2.5 border-b border-gray-700">
          <h3 className="text-xs font-semibold text-gray-400 tracking-widest uppercase">Site Assignment</h3>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-800/40 border-b border-gray-700">
              {['SITE REF', 'SITE TITLE', 'ASSIGNED', 'PRIMARY'].map(h => (
                <th key={h} className="text-left px-4 py-2.5 text-xs font-semibold text-gray-400 tracking-widest">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {[
              { ref: 'CTS', title: 'Captain Taxi Saskatoon', val: 'saskatoon' },
              { ref: 'CTR', title: 'Captain Taxi Regina',    val: 'regina'    },
            ].map(site => (
              <tr key={site.ref} className="bg-gray-900/60">
                <td className="px-4 py-2.5 text-gray-400 font-mono text-xs">{site.ref}</td>
                <td className="px-4 py-2.5 text-gray-300 text-xs">{site.title}</td>
                <td className="px-4 py-2.5">
                  <span className="badge text-xs bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    Assigned
                  </span>
                </td>
                <td className="px-4 py-2.5">
                  <input
                    type="radio"
                    name="primary_site"
                    value={site.val}
                    checked={form.primary_site === site.val}
                    onChange={() => set('primary_site', site.val)}
                    className="accent-amber-500"
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Recent Trips ── */}
      <div className="overflow-hidden rounded-lg border border-gray-700">
        <div className="bg-gray-800 px-4 py-2.5 border-b border-gray-700">
          <h3 className="text-xs font-semibold text-gray-400 tracking-widest uppercase">Recent Trips</h3>
        </div>
        <div className="bg-gray-900/60 p-4">
          {!trips || trips.length === 0 ? (
            <p className="text-sm text-gray-600 text-center py-4">No trips yet</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-800 text-xs text-gray-500 uppercase tracking-wide">
                    <th className="text-left py-2 pr-4 font-medium">Pickup</th>
                    <th className="text-left py-2 pr-4 font-medium hidden sm:table-cell">Dropoff</th>
                    <th className="text-right py-2 pr-4 font-medium">Fare</th>
                    <th className="text-right py-2 font-medium hidden md:table-cell">Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800/50">
                  {trips.slice(0, 20).map(trip => (
                    <tr key={trip.id} className="text-gray-300">
                      <td className="py-2 pr-4 truncate max-w-[180px]">{trip.pickup || '—'}</td>
                      <td className="py-2 pr-4 truncate max-w-[180px] hidden sm:table-cell">{trip.dropoff || '—'}</td>
                      <td className="py-2 pr-4 text-right text-amber-400 font-medium">${trip.fare.toFixed(2)}</td>
                      <td className="py-2 text-right text-gray-500 text-xs hidden md:table-cell">
                        {trip.completed_at ? format(new Date(trip.completed_at), 'MMM d') : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* ── Send SMS ── */}
      <div className="overflow-hidden rounded-lg border border-gray-700">
        <div className="bg-gray-800 px-4 py-2.5 border-b border-gray-700">
          <h3 className="text-xs font-semibold text-gray-400 tracking-widest uppercase flex items-center gap-2">
            <MessageSquare size={13} /> Send SMS to Driver
          </h3>
        </div>
        <div className="bg-gray-900/60 p-4">
          <textarea
            className="input h-20 resize-none mb-3 text-sm w-full"
            placeholder="Type your message..."
            value={message}
            onChange={e => setMessage(e.target.value)}
          />
          {msgSent
            ? <span className="text-xs text-emerald-400 flex items-center gap-1"><CheckCircle size={12} /> Message sent!</span>
            : <button onClick={handleMessage} disabled={!message.trim()} className="btn-primary text-xs tracking-widest">SEND SMS</button>
          }
        </div>
      </div>

      {/* ── Activity Log ── */}
      <div className="overflow-hidden rounded-lg border border-gray-700">
        <div className="bg-gray-800 px-4 py-2.5 border-b border-gray-700">
          <h3 className="text-xs font-semibold text-gray-400 tracking-widest uppercase flex items-center gap-2">
            <Clock size={13} /> Activity Log
          </h3>
        </div>
        <div className="bg-gray-900/60">
          {!activityLog || activityLog.length === 0 ? (
            <p className="text-sm text-gray-600 text-center py-6">No activity recorded yet</p>
          ) : (
            <div className="divide-y divide-gray-800">
              {activityLog.map(log => (
                <div key={log.id} className="flex items-start gap-3 px-4 py-3">
                  <div className={clsx('mt-0.5 shrink-0', {
                    'text-red-400':     log.action === 'suspended',
                    'text-emerald-400': log.action === 'activated',
                    'text-blue-400':    log.action === 'sms_sent',
                    'text-amber-400':   log.action === 'profile_updated',
                    'text-purple-400':  log.action === 'hr_drafted',
                    'text-gray-400':    !['suspended','activated','sms_sent','profile_updated','hr_drafted'].includes(log.action),
                  })}>
                    {log.action === 'suspended'       && <UserX      size={14} />}
                    {log.action === 'activated'       && <UserCheck   size={14} />}
                    {log.action === 'sms_sent'        && <Send        size={14} />}
                    {log.action === 'profile_updated' && <Save        size={14} />}
                    {log.action === 'hr_drafted'      && <FileText    size={14} />}
                    {log.action === 'created'         && <CheckCircle size={14} />}
                    {!['suspended','activated','sms_sent','profile_updated','hr_drafted','created'].includes(log.action) && <Clock size={14} />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-semibold text-gray-300 capitalize">
                        {log.action.replace(/_/g, ' ')}
                      </span>
                      <span className="text-xs text-gray-600 shrink-0">
                        {format(new Date(log.created_at), 'MMM d, yyyy h:mm a')}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5">{log.details}</p>
                    <p className="text-xs text-gray-700 mt-0.5">by {log.performed_by}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── HR Document Drafting ── */}
      <div className="overflow-hidden rounded-lg border border-gray-700">
        <div className="bg-gray-800 px-4 py-2.5 border-b border-gray-700">
          <h3 className="text-xs font-semibold text-gray-400 tracking-widest uppercase flex items-center gap-2">
            <AlertOctagon size={13} /> Draft HR Document
          </h3>
        </div>
        <div className="bg-gray-900/60 p-4">
          <div className="flex gap-3 mb-4">
            <select
              className="input flex-1 text-sm"
              value={hrType}
              onChange={e => setHrType(e.target.value)}
            >
              <option value="offer_letter">Offer Letter</option>
              <option value="warning_letter">Warning Letter</option>
              <option value="policy_update">Policy Update</option>
              <option value="termination">Termination Letter</option>
            </select>
            <button onClick={handleDraftHR} disabled={hrLoading} className="btn-primary text-xs tracking-widest">
              {hrLoading ? 'DRAFTING...' : 'DRAFT WITH AI'}
            </button>
          </div>
          {hrDraft && (
            <textarea
              className="input h-64 resize-y font-mono text-xs w-full"
              value={hrDraft}
              onChange={e => setHrDraft(e.target.value)}
            />
          )}
        </div>
      </div>

    </div>
  )
}
