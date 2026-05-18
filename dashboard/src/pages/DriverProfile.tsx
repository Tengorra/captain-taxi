import { useParams, useNavigate } from 'react-router-dom'
import { useState, useEffect, useRef } from 'react'
import { useApi } from '../hooks/useApi'
import { api } from '../lib/api'
import {
  ArrowLeft, Save, AlertOctagon, MessageSquare, CheckCircle, Clock,
  UserX, UserCheck, FileText, Send, Upload, Trash2, Download,
} from 'lucide-react'
import clsx from 'clsx'
import { format } from 'date-fns'
import type { Driver, DriverDocument } from '../types'

type DriverFile = { id: string; type: string; filename: string; uploaded_at: string }

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

function DocSlot({
  label, fileType, driverId, file, complianceDoc, onChanged,
}: {
  label: string
  fileType: string
  driverId: string
  file?: DriverFile
  complianceDoc?: DriverDocument
  onChanged: () => void
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (!f) return
    setBusy(true); setError('')
    try {
      await api.uploadDriverFile(driverId, fileType, f)
      onChanged()
    } catch (err) {
      setError((err as Error).message || 'Upload failed')
    } finally {
      setBusy(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  const handleDelete = async () => {
    if (!file) return
    if (!confirm(`Delete ${file.filename}?`)) return
    setBusy(true)
    try {
      await api.deleteDriverFile(driverId, file.id)
      onChanged()
    } finally { setBusy(false) }
  }

  return (
    <div className="p-4 border-gray-700 bg-gray-900/60">
      <p className="text-xs font-semibold text-gray-400 tracking-widest uppercase mb-3">{label}</p>
      {file ? (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-xs text-emerald-300">
            <FileText size={13} />
            <span className="truncate flex-1" title={file.filename}>{file.filename}</span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-gray-500">
              {file.uploaded_at ? format(new Date(file.uploaded_at), 'MMM d, yyyy') : '—'}
            </span>
            <div className="flex items-center gap-1.5">
              <a
                href={`/api/drivers/${driverId}/files/${file.id}/download`}
                className="p-1 text-gray-400 hover:text-amber-400 transition-colors"
                title="Download"
              ><Download size={13} /></a>
              <button
                onClick={handleDelete}
                disabled={busy}
                className="p-1 text-gray-400 hover:text-red-400 transition-colors disabled:opacity-50"
                title="Delete"
              ><Trash2 size={13} /></button>
            </div>
          </div>
        </div>
      ) : complianceDoc ? (
        <div className="flex items-center justify-between gap-2">
          <span className={clsx('badge text-xs capitalize', DOC_STATUS_CLS[complianceDoc.status] ?? 'bg-gray-700 text-gray-400')}>
            {complianceDoc.status.replace('_', ' ')}
          </span>
          {complianceDoc.expiry_date && (
            <span className="text-xs text-gray-500">
              {format(new Date(complianceDoc.expiry_date), 'MMM d, yyyy')}
            </span>
          )}
        </div>
      ) : (
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-600">{busy ? 'UPLOADING…' : 'NO FILE'}</span>
          <label className={clsx(
            'text-xs px-2 py-1 rounded transition-colors tracking-wide flex items-center gap-1',
            busy
              ? 'bg-gray-800 text-gray-600 cursor-not-allowed'
              : 'bg-gray-700 hover:bg-gray-600 text-gray-300 cursor-pointer',
          )}>
            <Upload size={11} /> UPLOAD
            <input ref={inputRef} type="file" className="hidden" onChange={handleUpload} disabled={busy} />
          </label>
        </div>
      )}
      {error && <p className="text-[10px] text-red-400 mt-1">{error}</p>}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

type FormState = Omit<
  Driver,
  'id' | 'total_trips' | 'total_earnings' | 'documents' | 'files' | 'created_at' | 'performance_score'
> & {
  // login_password is write-only — never returned from the API
  login_password?: string
  // primary_site is local UI state derived from `sites[]`
  primary_site?: string
}

const DAYS = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']

const DOC_SLOTS = [
  { key: 'police_disclosure', label: 'POLICE DISCLOSURE' },
  { key: 'agreement',         label: 'AGREEMENT'         },
  { key: 'proof_of_address',  label: 'PROOF OF ADDRESS'  },
  { key: 'photo_id',          label: 'PHOTO ID'          },
  { key: 'licence_photo',     label: 'LICENCE PHOTO'     },
  { key: 'licence_paper',     label: 'LICENCE PAPER'     },
  { key: 'pco_licence',       label: 'PCO LICENCE'       },
  { key: 'insurance',         label: 'INSURANCE'         },
]

const SITES = [
  { code: 'CTS', name: 'Captain Taxi Saskatoon' },
  { code: 'CTR', name: 'Captain Taxi Regina'    },
] as const

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
    first_name: '', last_name: '', aka: '', address: '',
    mobile_phone: '', other_phone: '', sex: 'male', ethnicity: '',
    transporter: false, login_username: '', login_password: '',
    driver_type: 'regular',
    badge_number: '', badge_expiry: '', badge_type: 'hackney',
    licence_number: '', licence_expiry: '', tax_number: '',
    pvg_disclosure: '',
    accept_discount: true, accept_account: true,
    accept_cash_work: true, accept_fixed_fares: true,
    attr_pets: false, attr_uniformed: false, attr_topman: false,
    attr_accept_discount: true, attr_accept_account: true,
    attr_accept_fixed_fares: true, attr_accept_cash_work: true,
    device_imei: '', phone_assist: false,
    payment_on: 'sunday', payment_type: 'cash',
    payment_on_day: 'sunday',
    bank_name: '', bank_account_number: '', sort_code: '',
    bank_account_name: '', bank_payment_ref: '', use_sepa: false,
    distribution: 'POST', apply_vat: false, vat_rate: 0,
    exclude_booking_fee: false, auto_post: 'SYSTEM_DEFAULT',
    invoice_footer: '', shift_reporting: false,
    police_record: '', police_record_2: '',
    breathalyser_enabled: false,
    fatigue_max_work_hours: 0, fatigue_min_rest_hours: 0,
    fatigue_exceed_job_pct: 0, fatigue_send_alert_pct: 0,
    primary_site: 'CTS',
    notes: '',
  })

  // Site assignments — local UI state, synced from `driver.sites`.
  const [siteSel, setSiteSel] = useState<Record<string, { assigned: boolean; primary: boolean }>>(
    Object.fromEntries(SITES.map(s => [s.code, { assigned: false, primary: false }]))
  )

  // Driver files (HR uploads — separate from compliance documents).
  const [files, setFiles] = useState<DriverFile[]>([])
  const reloadFiles = async () => {
    if (!id) return
    try { setFiles(await api.listDriverFiles(id)) } catch { /* ignore */ }
  }
  useEffect(() => { reloadFiles() /* eslint-disable-line */ }, [id])

  useEffect(() => {
    if (!driver) return
    const d = driver
    setForm({
      name: d.name ?? '',
      phone: d.phone ?? '',
      email: d.email ?? '',
      city: d.city ?? 'saskatoon',
      status: d.status ?? 'active',
      commission_rate: d.commission_rate ?? 0.3,
      vehicle_plate: d.vehicle_plate ?? '',
      vehicle_model: d.vehicle_model ?? '',
      first_name: d.first_name ?? '',
      last_name: d.last_name ?? '',
      aka: d.aka ?? '',
      address: d.address ?? '',
      mobile_phone: d.mobile_phone ?? d.mobile ?? '',
      other_phone: d.other_phone ?? '',
      sex: d.sex ?? (d.gender as Driver['sex']) ?? 'male',
      ethnicity: d.ethnicity ?? '',
      transporter: d.transporter ?? false,
      login_username: d.login_username ?? '',
      login_password: '',
      driver_type: d.driver_type ?? 'regular',
      badge_number: d.badge_number ?? '',
      badge_expiry: d.badge_expiry?.slice(0, 10) ?? '',
      badge_type: d.badge_type ?? 'hackney',
      licence_number: d.licence_number ?? '',
      licence_expiry: d.licence_expiry?.slice(0, 10) ?? '',
      tax_number: d.tax_number ?? '',
      pvg_disclosure: d.pvg_disclosure ?? '',
      // Legacy keys (kept for backward compat with existing UI bindings)
      accept_discount: d.attr_accept_discount ?? d.accept_discount ?? true,
      accept_account: d.attr_accept_account ?? d.accept_account ?? true,
      accept_cash_work: d.attr_accept_cash_work ?? d.accept_cash_work ?? true,
      accept_fixed_fares: d.attr_accept_fixed_fares ?? d.accept_fixed_fares ?? true,
      // New attribute fields
      attr_pets: d.attr_pets ?? false,
      attr_uniformed: d.attr_uniformed ?? false,
      attr_topman: d.attr_topman ?? false,
      attr_accept_discount: d.attr_accept_discount ?? true,
      attr_accept_account: d.attr_accept_account ?? true,
      attr_accept_fixed_fares: d.attr_accept_fixed_fares ?? true,
      attr_accept_cash_work: d.attr_accept_cash_work ?? true,
      device_imei: d.device_imei ?? '',
      phone_assist: d.phone_assist ?? false,
      payment_on: d.payment_on ?? 'sunday',
      payment_on_day: d.payment_on_day ?? d.payment_on ?? 'sunday',
      payment_type: d.payment_type ?? 'cash',
      bank_name: d.bank_name ?? '',
      bank_account_number: d.bank_account_number ?? '',
      sort_code: d.sort_code ?? '',
      bank_account_name: d.bank_account_name ?? '',
      bank_payment_ref: d.bank_payment_ref ?? '',
      use_sepa: d.use_sepa ?? false,
      distribution: d.distribution ?? 'POST',
      apply_vat: d.apply_vat ?? false,
      vat_rate: d.vat_rate ?? 0,
      exclude_booking_fee: d.exclude_booking_fee ?? false,
      auto_post: d.auto_post ?? 'SYSTEM_DEFAULT',
      invoice_footer: d.invoice_footer ?? '',
      shift_reporting: d.shift_reporting ?? false,
      police_record: d.police_record ?? '',
      police_record_2: d.police_record_2 ?? '',
      breathalyser_enabled: d.breathalyser_enabled ?? false,
      fatigue_max_work_hours: d.fatigue_max_work_hours ?? 0,
      fatigue_min_rest_hours: d.fatigue_min_rest_hours ?? 0,
      fatigue_exceed_job_pct: d.fatigue_exceed_job_pct ?? 0,
      fatigue_send_alert_pct: d.fatigue_send_alert_pct ?? 0,
      primary_site: d.sites?.find(s => s.is_primary)?.site_code ?? 'CTS',
      notes: d.notes ?? '',
    })
    // Hydrate site selection from server state
    const next: Record<string, { assigned: boolean; primary: boolean }> =
      Object.fromEntries(SITES.map(s => [s.code, { assigned: false, primary: false }]))
    if (d.sites && d.sites.length) {
      for (const s of d.sites) {
        if (next[s.site_code]) next[s.site_code] = { assigned: !!s.assigned, primary: !!s.is_primary }
      }
    }
    setSiteSel(next)
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
      const sites = SITES
        .filter(s => siteSel[s.code]?.assigned)
        .map(s => ({
          site_code: s.code,
          assigned: true,
          is_primary: !!siteSel[s.code]?.primary,
        }))
      await api.updateDriver(id!, {
        // Identity & contact
        first_name: form.first_name, last_name: form.last_name,
        aka: form.aka, address: form.address, email: form.email,
        phone: form.phone, mobile: form.mobile_phone,
        other_phone: form.other_phone, sex: form.sex,
        ethnicity: form.ethnicity, transporter: form.transporter,
        city: form.city, status: form.status, driver_type: form.driver_type,
        login_username: form.login_username,
        login_password: form.login_password || undefined,
        // Vehicle quick-edit
        vehicle_plate: form.vehicle_plate, vehicle_model: form.vehicle_model,
        // Licensing
        badge_number: form.badge_number, badge_expiry: form.badge_expiry,
        badge_type: form.badge_type,
        licence_number: form.licence_number, licence_expiry: form.licence_expiry,
        tax_number: form.tax_number, pvg_disclosure: form.pvg_disclosure,
        // Attributes
        attr_pets: form.attr_pets, attr_uniformed: form.attr_uniformed,
        attr_topman: form.attr_topman,
        attr_accept_discount: form.attr_accept_discount,
        attr_accept_account: form.attr_accept_account,
        attr_accept_fixed_fares: form.attr_accept_fixed_fares,
        attr_accept_cash_work: form.attr_accept_cash_work,
        // Custom
        police_record: form.police_record, police_record_2: form.police_record_2,
        breathalyser_enabled: form.breathalyser_enabled,
        // Device
        imei_udid: form.device_imei, phone_assist: form.phone_assist,
        // Invoicing / VAT / bank
        commission_rate: form.commission_rate,
        payment_type: form.payment_type, payment_on_day: form.payment_on_day,
        distribution: form.distribution, apply_vat: form.apply_vat,
        vat_rate: form.vat_rate, exclude_booking_fee: form.exclude_booking_fee,
        auto_post: form.auto_post, invoice_footer: form.invoice_footer,
        shift_reporting: form.shift_reporting,
        bank_name: form.bank_name, bank_account_name: form.bank_account_name,
        bank_account_number: form.bank_account_number, sort_code: form.sort_code,
        bank_payment_ref: form.bank_payment_ref, use_sepa: form.use_sepa,
        // Fatigue
        fatigue_max_work_hours: form.fatigue_max_work_hours,
        fatigue_min_rest_hours: form.fatigue_min_rest_hours,
        fatigue_exceed_job_pct: form.fatigue_exceed_job_pct,
        fatigue_send_alert_pct: form.fatigue_send_alert_pct,
        // Sites + notes
        sites,
        notes: form.notes,
      })
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
          <Field label="DRIVER ID">
            <input
              className="input w-full text-sm text-gray-500 cursor-not-allowed"
              value={driver.id.slice(0, 8).toUpperCase()}
              readOnly
            />
          </Field>
          <Field label="DRIVER LOGIN">
            <input {...inp('login_username')} placeholder="Username" />
          </Field>
          <Field label="PASSWORD">
            <input
              className="input w-full text-sm"
              type="password"
              placeholder={driver.has_login_password ? '••••••••  (leave blank to keep)' : 'Set a password'}
              value={form.login_password ?? ''}
              onChange={e => set('login_password', e.target.value)}
            />
          </Field>
          <Field label="PHONE">
            <input {...inp('phone')} />
          </Field>
          <Field label="TRANSPORTER">
            <select
              className="input w-full text-sm"
              value={form.transporter ? 'yes' : 'no'}
              onChange={e => set('transporter', e.target.value === 'yes')}
            >
              <option value="no">NO</option>
              <option value="yes">YES</option>
            </select>
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
          <Field label="ETHNICITY">
            <input {...inp('ethnicity')} />
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
          <Field label="TAX / NI NUMBER">
            <input {...inp('tax_number')} />
          </Field>
          <Field label="PVG DISCLOSURE">
            <textarea
              className="input w-full text-sm h-16 resize-none"
              value={(form.pvg_disclosure as string | undefined) ?? ''}
              onChange={e => set('pvg_disclosure', e.target.value)}
            />
          </Field>
        </Section>

        <Section title="Attributes">
          {([
            ['PETS',               'attr_pets'],
            ['UNIFORMED',          'attr_uniformed'],
            ['TOPMAN',             'attr_topman'],
            ['ACCEPT DISCOUNT',    'attr_accept_discount'],
            ['ACCEPT ACCOUNT',     'attr_accept_account'],
            ['ACCEPT CASH WORK',   'attr_accept_cash_work'],
            ['ACCEPT FIXED FARES', 'attr_accept_fixed_fares'],
          ] as const).map(([label, key]) => (
            <Field key={key} label={label}>
              <select
                className="input w-full text-sm"
                value={(form[key] as boolean | undefined) ? 'yes' : 'no'}
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

      {/* ── Row 3: Notes ── */}
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

      {/* ── Row 4: Invoicing / Shifts | Payments + VAT ── */}
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
            <select {...sel('payment_on_day')}>
              {DAYS.map(d => (
                <option key={d} value={d}>{d.charAt(0).toUpperCase() + d.slice(1)}</option>
              ))}
            </select>
          </Field>
          <Field label="INVOICE FOOTER">
            <select {...sel('invoice_footer')}>
              <option value="">NONE</option>
              <option value="STANDARD">Standard</option>
              <option value="VAT">VAT Footer</option>
            </select>
          </Field>
          <Field label="SHIFT REPORTING">
            <select
              className="input w-full text-sm"
              value={form.shift_reporting ? 'yes' : 'no'}
              onChange={e => set('shift_reporting', e.target.value === 'yes')}
            >
              <option value="no">NO</option>
              <option value="yes">YES</option>
            </select>
          </Field>
        </Section>

        <Section title="Payments / VAT">
          <Field label="PAYMENT TYPE">
            <select {...sel('payment_type')}>
              <option value="cash">Cash</option>
              <option value="bank_transfer">Bank Transfer</option>
              <option value="card">Card</option>
            </select>
          </Field>
          <Field label="DISTRIBUTION">
            <select {...sel('distribution')}>
              <option value="POST">Post</option>
              <option value="EMAIL">Email</option>
            </select>
          </Field>
          <Field label="APPLY VAT?">
            <select
              className="input w-full text-sm"
              value={form.apply_vat ? 'yes' : 'no'}
              onChange={e => set('apply_vat', e.target.value === 'yes')}
            >
              <option value="no">NO</option>
              <option value="yes">YES</option>
            </select>
          </Field>
          <Field label="VAT RATE (%)">
            <input
              className="input w-full text-sm"
              type="number"
              step="0.01"
              value={(form.vat_rate as number | undefined) ?? 0}
              onChange={e => set('vat_rate', Number(e.target.value))}
            />
          </Field>
          <Field label="EXCLUDE BOOKING FEE">
            <select
              className="input w-full text-sm"
              value={form.exclude_booking_fee ? 'yes' : 'no'}
              onChange={e => set('exclude_booking_fee', e.target.value === 'yes')}
            >
              <option value="no">NO</option>
              <option value="yes">YES</option>
            </select>
          </Field>
          <Field label="AUTO POST">
            <select {...sel('auto_post')}>
              <option value="SYSTEM_DEFAULT">System Default</option>
              <option value="NEVER">Never</option>
              <option value="ALWAYS">Always</option>
            </select>
          </Field>
          <Field label="BALANCE">
            <input
              className="input w-full text-sm text-gray-500 cursor-not-allowed"
              value={driver.balance != null ? `$${Number(driver.balance).toFixed(2)}` : '—'}
              readOnly
            />
          </Field>
        </Section>
      </div>

      {/* ── Row 5: Bank | Driver Fatigue ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        <Section title="Bank">
          <Field label="BANK PAYMENT REF">
            <input {...inp('bank_payment_ref')} />
          </Field>
          <Field label="USE SEPA">
            <select
              className="input w-full text-sm"
              value={form.use_sepa ? 'yes' : 'no'}
              onChange={e => set('use_sepa', e.target.value === 'yes')}
            >
              <option value="no">NO</option>
              <option value="yes">YES</option>
            </select>
          </Field>
          <Field label="BANK NAME">
            <input {...inp('bank_name')} />
          </Field>
          <Field label="ACCOUNT NAME">
            <input {...inp('bank_account_name')} />
          </Field>
          <Field label="SORT CODE">
            <input {...inp('sort_code')} />
          </Field>
          <Field label="ACCOUNT NUMBER">
            <input {...inp('bank_account_number')} />
          </Field>
        </Section>

        <Section title="Driver Fatigue">
          <Field label="MAX WORK HOURS">
            <input
              className="input w-full text-sm" type="number" min="0"
              value={(form.fatigue_max_work_hours as number | undefined) ?? 0}
              onChange={e => set('fatigue_max_work_hours', Number(e.target.value))}
            />
          </Field>
          <Field label="MIN REST HOURS">
            <input
              className="input w-full text-sm" type="number" min="0"
              value={(form.fatigue_min_rest_hours as number | undefined) ?? 0}
              onChange={e => set('fatigue_min_rest_hours', Number(e.target.value))}
            />
          </Field>
          <Field label="EXCEED JOB BY (%)">
            <input
              className="input w-full text-sm" type="number" min="0"
              value={(form.fatigue_exceed_job_pct as number | undefined) ?? 0}
              onChange={e => set('fatigue_exceed_job_pct', Number(e.target.value))}
            />
          </Field>
          <Field label="SEND ALERT AT (%)">
            <input
              className="input w-full text-sm" type="number" min="0" max="100"
              value={(form.fatigue_send_alert_pct as number | undefined) ?? 0}
              onChange={e => set('fatigue_send_alert_pct', Number(e.target.value))}
            />
          </Field>
        </Section>
      </div>

      {/* ── Row 6: Custom Fields | Device ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Section title="Custom Fields">
          <Field label="POLICE RECORD">
            <input {...inp('police_record')} />
          </Field>
          <Field label="POLICE RECORD 2">
            <input {...inp('police_record_2')} />
          </Field>
          <Field label="BREATHALYSER">
            <select
              className="input w-full text-sm"
              value={form.breathalyser_enabled ? 'yes' : 'no'}
              onChange={e => set('breathalyser_enabled', e.target.value === 'yes')}
            >
              <option value="no">NO</option>
              <option value="yes">YES</option>
            </select>
          </Field>
        </Section>

        <Section title="Device">
          <Field label="DEVICE IMEI / UID">
            <input {...inp('device_imei')} placeholder="IMEI or device UID" />
          </Field>
          <Field label="PHONE ASSIST">
            <select
              className="input w-full text-sm"
              value={form.phone_assist ? 'yes' : 'no'}
              onChange={e => set('phone_assist', e.target.value === 'yes')}
            >
              <option value="no">NO</option>
              <option value="yes">YES</option>
            </select>
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
            const file = files.find(f => f.type === key)
            const complianceDoc = driver.documents?.find(d => d.type === key)
            return (
              <DocSlot
                key={key}
                label={label}
                fileType={key}
                driverId={id!}
                file={file}
                complianceDoc={complianceDoc}
                onChanged={reloadFiles}
              />
            )
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
            {SITES.map(s => (
              <tr key={s.code} className="bg-gray-900/60">
                <td className="px-4 py-2.5 text-amber-300 font-mono text-xs">{s.code}</td>
                <td className="px-4 py-2.5 text-gray-300 text-xs">{s.name}</td>
                <td className="px-4 py-2.5">
                  <label className="inline-flex items-center gap-2 text-xs">
                    <input
                      type="checkbox"
                      checked={!!siteSel[s.code]?.assigned}
                      onChange={e => setSiteSel(prev => ({
                        ...prev,
                        [s.code]: {
                          assigned: e.target.checked,
                          primary: e.target.checked ? prev[s.code].primary : false,
                        }
                      }))}
                    />
                    <span className={clsx(siteSel[s.code]?.assigned ? 'text-emerald-400' : 'text-gray-500')}>
                      {siteSel[s.code]?.assigned ? 'Assigned' : 'Not assigned'}
                    </span>
                  </label>
                </td>
                <td className="px-4 py-2.5">
                  <input
                    type="radio"
                    name="primary_site"
                    checked={!!siteSel[s.code]?.primary}
                    disabled={!siteSel[s.code]?.assigned}
                    onChange={() => setSiteSel(prev => {
                      const next: typeof prev = {}
                      for (const code of Object.keys(prev)) {
                        next[code] = { assigned: prev[code].assigned, primary: code === s.code }
                      }
                      return next
                    })}
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
