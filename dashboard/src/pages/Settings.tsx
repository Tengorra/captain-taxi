import { useEffect, useState } from 'react'
import { useApi, useMutation } from '../hooks/useApi'
import { api } from '../lib/api'
import { Save, CheckCircle, Megaphone, Send, Plus, RefreshCw, Cloud } from 'lucide-react'

const SETTING_GROUPS = [
  {
    title: 'Commission Rates',
    keys: ['commission_rate_saskatoon', 'commission_rate_regina'],
    format: (v: string) => `${Math.round(parseFloat(v) * 100)}%`,
    type: 'percent',
  },
  {
    title: 'Alerts & Digests',
    keys: ['digest_hour', 'escalation_timeout_hours', 'low_driver_threshold'],
    type: 'number',
  },
  {
    title: 'Notifications',
    keys: ['owner_alerts_enabled', 'amara_alerts_enabled', 'weekly_report_day'],
    type: 'text',
  },
]

export default function Settings() {
  const { data: settings, loading, reload } = useApi(() => api.getSettings(), [])
  const [edits, setEdits] = useState<Record<string, string>>({})
  const [saved, setSaved] = useState<Record<string, boolean>>({})

  const { mutate: updateSetting } = useMutation(
    (key: string, value: string) => api.updateSetting(key, value)
  )

  const [announcement, setAnnouncement] = useState('')
  const [annCity, setAnnCity] = useState('')
  const [annResult, setAnnResult] = useState<any>(null)
  const [annLoading, setAnnLoading] = useState(false)

  // ── Driver mandatory fields editor ──
  // Server-side list of state-key names the manual Add-Driver form requires.
  // Stored as a JSON-string Settings row so it round-trips through the same
  // PUT /api/settings/{key} endpoint as everything else here.
  const DRIVER_FIELD_OPTIONS = [
    'first_name', 'last_name', 'phone', 'mobile_phone', 'email',
    'address', 'sex', 'city', 'badge_number', 'badge_expiry', 'badge_type',
    'licence_number', 'licence_expiry', 'vehicle_plate', 'vehicle_make',
    'vehicle_model', 'driver_type',
  ]
  const [reqFields, setReqFields] = useState<string[]>([])
  const [reqDirty, setReqDirty] = useState(false)
  const [reqSaved, setReqSaved] = useState(false)
  useEffect(() => {
    const raw = settings?.driver_mandatory_fields?.value
    if (raw) {
      try {
        const parsed = JSON.parse(raw)
        if (Array.isArray(parsed)) setReqFields(parsed.map(String))
      } catch { /* ignore */ }
    }
  }, [settings])
  const toggleReq = (k: string) => {
    setReqFields(prev => {
      const next = prev.includes(k) ? prev.filter(x => x !== k) : [...prev, k]
      setReqDirty(true)
      return next
    })
  }
  const saveReq = async () => {
    await updateSetting('driver_mandatory_fields', JSON.stringify(reqFields))
    setReqDirty(false); setReqSaved(true); reload()
    setTimeout(() => setReqSaved(false), 2000)
  }

  // ── iCabbi sync panel ──
  const [icabbi, setIcabbi] = useState<{ configured: boolean; entities: string[] } | null>(null)
  const [syncLoading, setSyncLoading] = useState(false)
  const [syncResult, setSyncResult] = useState<any>(null)
  useEffect(() => { api.getIcabbiStatus().then(setIcabbi).catch(() => setIcabbi(null)) }, [])
  const runSync = async () => {
    setSyncLoading(true); setSyncResult(null)
    try { setSyncResult(await api.triggerIcabbiSync()) }
    catch (e: any) { setSyncResult({ ok: false, error: e?.message || String(e) }) }
    finally { setSyncLoading(false) }
  }

  const handleSave = async (key: string) => {
    const value = edits[key]
    if (!value) return
    await updateSetting(key, value)
    setSaved({ ...saved, [key]: true })
    setTimeout(() => setSaved(s => ({ ...s, [key]: false })), 2000)
    reload()
  }

  const handleAnnouncement = async () => {
    if (!announcement.trim()) return
    setAnnLoading(true)
    try {
      const result = await api.sendAnnouncement(announcement, annCity || undefined)
      setAnnResult(result)
      setAnnouncement('')
    } finally {
      setAnnLoading(false)
    }
  }

  const getDisplayValue = (key: string) => {
    if (edits[key] !== undefined) return edits[key]
    return settings?.[key]?.value ?? ''
  }

  return (
    <div className="space-y-6 max-w-2xl">

      {/* Settings groups */}
      {SETTING_GROUPS.map(group => (
        <div key={group.title} className="card">
          <h2 className="font-semibold text-sm text-gray-300 mb-4">{group.title}</h2>
          <div className="space-y-4">
            {group.keys.map(key => {
              const setting = settings?.[key]
              return (
                <div key={key}>
                  <label className="label">
                    {key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                  </label>
                  {setting?.description && (
                    <p className="text-xs text-gray-600 mb-1">{setting.description}</p>
                  )}
                  <div className="flex gap-2">
                    <input
                      className="input"
                      value={getDisplayValue(key)}
                      onChange={e => setEdits({ ...edits, [key]: e.target.value })}
                      disabled={loading}
                    />
                    <button
                      onClick={() => handleSave(key)}
                      className={saved[key] ? 'btn-success' : 'btn-ghost'}
                      disabled={edits[key] === undefined || edits[key] === settings?.[key]?.value}
                    >
                      {saved[key] ? <CheckCircle size={15} /> : <Save size={15} />}
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      ))}

      {/* Driver Add-form required fields */}
      <div className="card">
        <h2 className="font-semibold text-sm text-gray-300 mb-1 flex items-center gap-2">
          <Plus size={15} /> Driver Add-Form Required Fields
        </h2>
        <p className="text-xs text-gray-500 mb-3">
          Toggle which fields are required when staff add a driver manually. Stored as
          the <code className="text-amber-400">driver_mandatory_fields</code> setting.
        </p>
        <div className="flex flex-wrap gap-2 mb-3">
          {DRIVER_FIELD_OPTIONS.map(k => {
            const on = reqFields.includes(k)
            return (
              <button
                key={k}
                onClick={() => toggleReq(k)}
                className={`text-xs px-2.5 py-1 rounded-full border ${
                  on
                    ? 'bg-amber-500/15 text-amber-300 border-amber-500/40'
                    : 'bg-gray-800 text-gray-400 border-gray-700 hover:text-gray-200'
                }`}
              >
                {on ? <span className="mr-1">✓</span> : null}{k}
              </button>
            )
          })}
        </div>
        <button
          onClick={saveReq}
          className={reqSaved ? 'btn-success' : 'btn-primary'}
          disabled={!reqDirty || reqSaved}
        >
          {reqSaved ? <><CheckCircle size={15} /> Saved</> : <><Save size={15} /> Save Required Fields</>}
        </button>
      </div>

      {/* iCabbi sync */}
      <div className="card">
        <h2 className="font-semibold text-sm text-gray-300 mb-1 flex items-center gap-2">
          <Cloud size={15} /> iCabbi Sync
        </h2>
        {icabbi === null ? (
          <p className="text-xs text-gray-500">Loading status…</p>
        ) : icabbi.configured ? (
          <p className="text-xs text-emerald-400 mb-3">
            ✓ iCabbi credentials detected — sync is wired up.
          </p>
        ) : (
          <p className="text-xs text-amber-400 mb-3">
            ⚠ ICABBI_BASE_URL / ICABBI_API_KEY not set — sync will skip every entity.
          </p>
        )}
        {icabbi && (
          <p className="text-xs text-gray-500 mb-3">
            Entities: {icabbi.entities.join(', ')} · Auto-runs nightly at 3 AM.
          </p>
        )}
        <button onClick={runSync} className="btn-ghost" disabled={syncLoading}>
          <RefreshCw size={14} className={syncLoading ? 'animate-spin' : ''} />
          {syncLoading ? 'Syncing…' : 'Run Sync Now'}
        </button>
        {syncResult && (
          <pre className="mt-3 text-xs text-gray-400 bg-gray-900 border border-gray-800 rounded p-2 overflow-x-auto max-h-60">
            {JSON.stringify(syncResult, null, 2)}
          </pre>
        )}
      </div>

      {/* Announcement blaster */}
      <div className="card">
        <h2 className="font-semibold text-sm text-gray-300 mb-4 flex items-center gap-2">
          <Megaphone size={15} /> Broadcast Announcement
        </h2>
        <p className="text-xs text-gray-500 mb-3">
          Send an SMS to all active drivers. Use this for schedule changes, weather alerts, etc.
        </p>
        <div className="space-y-3">
          <div>
            <label className="label">Target City</label>
            <select className="input" value={annCity} onChange={e => setAnnCity(e.target.value)}>
              <option value="">All Cities (Saskatoon + Regina)</option>
              <option value="saskatoon">Saskatoon only</option>
              <option value="regina">Regina only</option>
            </select>
          </div>
          <div>
            <label className="label">Message</label>
            <textarea
              className="input h-24 resize-none"
              placeholder="Type your announcement..."
              value={announcement}
              onChange={e => setAnnouncement(e.target.value)}
            />
          </div>

          {annResult && (
            <div className="flex items-center gap-2 text-emerald-400 text-sm">
              <CheckCircle size={15} />
              Sent to {annResult.sent} driver{annResult.sent !== 1 ? 's' : ''}
              {annResult.failed > 0 && (
                <span className="text-red-400">· {annResult.failed} failed</span>
              )}
            </div>
          )}

          <button
            onClick={handleAnnouncement}
            className="btn-primary w-full"
            disabled={!announcement.trim() || annLoading}
          >
            <Send size={15} />
            {annLoading ? 'Sending...' : 'Send to All Drivers'}
          </button>
        </div>
      </div>

      {/* WhatsApp command reference */}
      <div className="card border border-gray-700 bg-gray-900/50">
        <h2 className="font-semibold text-sm text-gray-300 mb-3">WhatsApp Command Reference</h2>
        <p className="text-xs text-gray-500 mb-3">
          Send these messages to the system WhatsApp number for instant responses:
        </p>
        <div className="space-y-1.5 font-mono text-xs">
          {[
            ['drivers online', 'How many drivers are online per city'],
            ['revenue today', "Today's fare revenue"],
            ['escalations', 'List pending escalations'],
            ['approve [id]', 'Approve an escalation'],
            ['deny [id]', 'Deny an escalation'],
            ['suspend driver [name]', 'Suspend a driver immediately'],
            ['activate driver [name]', 'Re-activate a suspended driver'],
            ['help', 'Show all commands'],
          ].map(([cmd, desc]) => (
            <div key={cmd} className="flex gap-3 py-1 border-b border-gray-800 last:border-0">
              <span className="text-amber-400 w-44 flex-shrink-0">{cmd}</span>
              <span className="text-gray-500">{desc}</span>
            </div>
          ))}
        </div>
      </div>

    </div>
  )
}
