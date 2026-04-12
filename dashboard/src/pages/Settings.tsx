import { useState } from 'react'
import { useApi, useMutation } from '../hooks/useApi'
import { api } from '../lib/api'
import { Save, CheckCircle, Megaphone, Send } from 'lucide-react'

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
