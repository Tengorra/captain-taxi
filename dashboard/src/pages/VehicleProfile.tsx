import { useParams, useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { api } from '../lib/api'
import { ArrowLeft, Save, Trash2, CheckCircle, Car } from 'lucide-react'
import clsx from 'clsx'

type V = Record<string, unknown>

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
    <div className="grid items-center gap-3" style={{ gridTemplateColumns: '160px 1fr' }}>
      <label className="text-xs text-gray-400 tracking-wide text-right">{label}</label>
      <div>{children}</div>
    </div>
  )
}

// iCabbi exports times in MM/DD/YYYY HH:mm — internally we store ISO. The
// edit form uses native <input type="datetime-local"> which needs the
// 16-char "YYYY-MM-DDTHH:mm" form, so we crop accordingly.
function toLocalDT(s?: string): string {
  if (!s) return ''
  return s.slice(0, 16)
}

function toLocalDate(s?: string): string {
  if (!s) return ''
  return s.slice(0, 10)
}

const BODY_TYPES = [
  ['body_sedan',      'Sedan'],
  ['body_minivan',    'Minivan'],
  ['body_suv',        'SUV'],
  ['body_low_rider',  'Low Rider'],
  ['body_estate',     'Estate'],
  ['body_high_rider', 'High Rider'],
  ['saloon',          'Saloon'],
  ['executive',       'Executive'],
] as const

const SEATERS = [4, 5, 6, 7, 8] as const

export default function VehicleProfile() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [v, setV]               = useState<V | null>(null)
  const [form, setForm]         = useState<V>({})
  const [loading, setLoading]   = useState(true)
  const [saving, setSaving]     = useState(false)
  const [savedAt, setSavedAt]   = useState(0)
  const [error, setError]       = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    api.getVehicle(id!)
      .then(data => {
        if (cancelled) return
        setV(data)
        setForm({ ...data })
      })
      .catch(e => setError(e.message || 'Failed to load vehicle'))
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [id])

  const set = (key: string, val: unknown) => setForm(f => ({ ...f, [key]: val }))

  const handleSave = async () => {
    setSaving(true); setError('')
    try {
      // Normalise datetime-local back to ISO (the backend re-parses anyway,
      // but sending "T" form keeps the wire format stable across re-saves).
      const payload: V = { ...form }
      for (const k of ['nct_mot_expiry', 'plate_expiry', 'road_tax_expiry',
                       'council_compliance_expiry', 'hire_expiry']) {
        if (typeof payload[k] === 'string' && (payload[k] as string).length === 16) {
          payload[k] = (payload[k] as string) + ':00'
        }
      }
      const updated = await api.updateVehicle(id!, payload)
      setV(updated)
      setForm({ ...updated })
      setSavedAt(Date.now())
    } catch (e) {
      setError((e as Error).message || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!confirm(`Soft-delete vehicle ${v?.vehicle_ref || v?.plate}?`)) return
    await api.deleteVehicle(id!)
    navigate('/vehicles')
  }

  const inp = (key: string) => ({
    className: 'input w-full text-sm',
    value: (form[key] as string | undefined) ?? '',
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => set(key, e.target.value),
  })

  const yn = (key: string) => (
    <select
      className="input w-full text-sm"
      value={form[key] ? 'yes' : 'no'}
      onChange={e => set(key, e.target.value === 'yes')}
    >
      <option value="no">NO</option>
      <option value="yes">YES</option>
    </select>
  )

  if (loading) return (
    <div className="space-y-4">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="h-24 bg-gray-800 rounded animate-pulse" />
      ))}
    </div>
  )

  if (!v) return (
    <div className="card text-center py-16 text-gray-600">
      Vehicle not found
      {error && <p className="text-xs text-red-400 mt-2">{error}</p>}
    </div>
  )

  const driver = v.driver as { id: string; name: string } | null | undefined

  return (
    <div className="space-y-4 max-w-6xl">

      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <button onClick={() => navigate('/vehicles')} className="flex items-center gap-1.5 hover:text-white transition-colors">
            <ArrowLeft size={13} /> Vehicles
          </button>
          <span className="text-gray-600">&gt;&gt;</span>
          <span className="text-white font-semibold tracking-wide flex items-center gap-2">
            <Car size={14} className="text-amber-400" />
            {(v.vehicle_ref as string) || (v.plate as string) || (v.id as string).slice(0, 8).toUpperCase()}
          </span>
          {v.is_deleted ? (
            <span className="badge bg-red-500/10 text-red-400 border border-red-500/20 text-xs">DELETED</span>
          ) : v.is_active ? (
            <span className="badge bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs">ACTIVE</span>
          ) : (
            <span className="badge bg-gray-800 text-gray-500 text-xs">INACTIVE</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {Date.now() - savedAt < 3000 && (
            <span className="text-xs text-emerald-400 flex items-center gap-1">
              <CheckCircle size={12} /> Saved
            </span>
          )}
          {!v.is_deleted && (
            <button onClick={handleDelete} className="btn-danger flex items-center gap-1 text-xs px-4 tracking-widest">
              <Trash2 size={12} /> DELETE
            </button>
          )}
          <button onClick={handleSave} disabled={saving} className="btn-primary flex items-center gap-2 text-xs px-5 tracking-widest">
            <Save size={13} />
            {saving ? 'SAVING…' : 'SAVE'}
          </button>
        </div>
      </div>
      {error && <div className="p-3 rounded bg-red-500/10 border border-red-500/20 text-red-400 text-sm">{error}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        <Section title="Identity">
          <Field label="VEHICLE REF"><input {...inp('vehicle_ref')} /></Field>
          <Field label="A.K.A."><input {...inp('aka')} /></Field>
          <Field label="INTERNAL SYSTEM ID"><input {...inp('internal_system_id')} /></Field>
          <Field label="PLATE"><input {...inp('plate')} className="input w-full text-sm uppercase" /></Field>
          <Field label="REGISTRATION"><input {...inp('registration')} /></Field>
          <Field label="VEHICLE PHONE"><input {...inp('vehicle_phone')} /></Field>
          <Field label="DRIVER">
            {driver ? (
              <button
                onClick={() => navigate(`/drivers/${driver.id}`)}
                className="text-xs text-amber-300 hover:text-amber-400 underline-offset-2 hover:underline truncate text-left"
                title={driver.name}
              >
                {driver.name}
              </button>
            ) : <span className="text-xs text-gray-600">Unassigned</span>}
          </Field>
          <Field label="CITY">
            <select
              className="input w-full text-sm"
              value={(form.city as string | undefined) ?? ''}
              onChange={e => set('city', e.target.value)}
            >
              <option value="">—</option>
              <option value="saskatoon">Saskatoon</option>
              <option value="regina">Regina</option>
            </select>
          </Field>
        </Section>

        <Section title="Make / Model">
          <Field label="MAKE"><input {...inp('make')} /></Field>
          <Field label="MODEL"><input {...inp('model')} /></Field>
          <Field label="COLOR"><input {...inp('color')} /></Field>
          <Field label="YEAR">
            <input
              className="input w-full text-sm" type="number"
              value={(form.year as number | undefined) ?? ''}
              onChange={e => set('year', e.target.value ? Number(e.target.value) : undefined)}
            />
          </Field>
          <Field label="OWNER DRIVER">{yn('owner_driver')}</Field>
          <Field label="CO2 EMISSION">
            <input
              className="input w-full text-sm" type="number" step="0.1"
              value={(form.co2_emission as number | undefined) ?? ''}
              onChange={e => set('co2_emission', e.target.value ? Number(e.target.value) : undefined)}
            />
          </Field>
          <Field label="COMMENTS">
            <textarea
              className="input w-full text-sm h-16 resize-none"
              value={(form.comments as string | undefined) ?? ''}
              onChange={e => set('comments', e.target.value)}
            />
          </Field>
        </Section>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Section title="Insurance & Compliance">
          <Field label="INSURER"><input {...inp('insurer')} /></Field>
          <Field label="INSURANCE POLICY"><input {...inp('insurance')} /></Field>
          <Field label="INSURANCE EXPIRY">
            <input
              className="input w-full text-sm" type="date"
              value={toLocalDate(form.insurance_expiry as string | undefined)}
              onChange={e => set('insurance_expiry', e.target.value)}
            />
          </Field>
          <Field label="PLATE EXPIRY">
            <input
              className="input w-full text-sm" type="datetime-local"
              value={toLocalDT(form.plate_expiry as string | undefined)}
              onChange={e => set('plate_expiry', e.target.value)}
            />
          </Field>
          <Field label="NCT/MOT EXPIRY">
            <input
              className="input w-full text-sm" type="datetime-local"
              value={toLocalDT(form.nct_mot_expiry as string | undefined)}
              onChange={e => set('nct_mot_expiry', e.target.value)}
            />
          </Field>
          <Field label="ROAD TAX EXPIRY">
            <input
              className="input w-full text-sm" type="datetime-local"
              value={toLocalDT(form.road_tax_expiry as string | undefined)}
              onChange={e => set('road_tax_expiry', e.target.value)}
            />
          </Field>
          <Field label="HIRE EXPIRY">
            <input
              className="input w-full text-sm" type="datetime-local"
              value={toLocalDT(form.hire_expiry as string | undefined)}
              onChange={e => set('hire_expiry', e.target.value)}
            />
          </Field>
          <Field label="COUNCIL COMPLIANCE">
            <input
              className="input w-full text-sm" type="datetime-local"
              value={toLocalDT(form.council_compliance_expiry as string | undefined)}
              onChange={e => set('council_compliance_expiry', e.target.value)}
            />
          </Field>
        </Section>

        <Section title="Device & Payments">
          <Field label="DEVICE IDENTIFIER"><input {...inp('device_identifier')} /></Field>
          <Field label="SENSORS"><input {...inp('sensors')} /></Field>
          <Field label="PAYMENT DEVICE"><input {...inp('payment_device')} /></Field>
          <Field label="PAYMENT VERSION"><input {...inp('payment_version')} /></Field>
          <Field label="LIGHT CONTROL"><input {...inp('light_control')} /></Field>
          <Field label="STATUS CONTROL"><input {...inp('status_control')} /></Field>
          <Field label="CREDIT CARD">{yn('credit_card_payments')}</Field>
          <Field label="WI-FI">{yn('wifi')}</Field>
        </Section>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Section title="Body Type">
          {BODY_TYPES.map(([key, label]) => (
            <Field key={key} label={label.toUpperCase()}>
              {yn(key)}
            </Field>
          ))}
        </Section>

        <Section title="Capacity & Accessibility">
          {SEATERS.map(n => (
            <Field key={n} label={`${n} SEATER`}>
              {yn(`seater_${n}`)}
            </Field>
          ))}
          <Field label="WHEELCHAIR">{yn('wheelchair')}</Field>
          <Field label="GOOD CONDITION">{yn('good_condition')}</Field>
          <Field label="AVERAGE CONDITION">{yn('average_condition')}</Field>
        </Section>
      </div>

      <Section title="Status">
        <Field label="ACTIVE">{yn('is_active')}</Field>
        <Field label="DELETED">
          {/* Read-only display — use the DELETE button to soft-delete. */}
          <span className={clsx('badge text-xs', v.is_deleted
            ? 'bg-red-500/10 text-red-400 border border-red-500/20'
            : 'bg-gray-800 text-gray-500 border border-gray-700')}>
            {v.is_deleted ? 'YES' : 'NO'}
          </span>
        </Field>
      </Section>
    </div>
  )
}
