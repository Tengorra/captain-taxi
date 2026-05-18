import { useState } from 'react'
import { useApi, useMutation } from '../hooks/useApi'
import { Plus, Trash2, RefreshCw } from 'lucide-react'

export interface FieldDef {
  key: string
  label: string
  type?: 'text' | 'number' | 'bool' | 'select'
  options?: string[]
  required?: boolean
  placeholder?: string
}

export interface ModulePageProps {
  title: string
  description?: string
  fields: FieldDef[]
  columns: { key: string; label: string; format?: (v: any) => React.ReactNode }[]
  list: () => Promise<any[]>
  create: (data: Record<string, unknown>) => Promise<any>
  remove?: (id: number) => Promise<any>
  defaults?: Record<string, unknown>
  headerExtra?: (reload: () => void) => React.ReactNode
}

export default function ModulePage(p: ModulePageProps) {
  const { data, loading, reload } = useApi(p.list, [])
  const [form, setForm] = useState<Record<string, any>>(p.defaults || {})
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const { mutate: doCreate, loading: creating } = useMutation(
    async (payload: Record<string, unknown>) => p.create(payload)
  )
  const { mutate: doRemove } = useMutation(async (id: number) =>
    p.remove ? p.remove(id) : Promise.resolve()
  )

  const submit = async () => {
    setError(null)
    const payload: Record<string, unknown> = {}
    for (const f of p.fields) {
      const v = form[f.key]
      if (f.required && (v === undefined || v === '' || v === null)) {
        setError(`Missing required field: ${f.label}`); return
      }
      if (v !== undefined && v !== '' && v !== null) {
        payload[f.key] = f.type === 'number' ? Number(v) : f.type === 'bool' ? Boolean(v) : v
      }
    }
    try {
      await doCreate(payload)
      setForm(p.defaults || {}); setOpen(false); reload()
    } catch (e: any) {
      setError(e?.message || 'Create failed')
    }
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">{p.title}</h1>
          {p.description && <p className="text-sm text-gray-400 mt-1">{p.description}</p>}
        </div>
        <div className="flex gap-2 items-center">
          {p.headerExtra?.(reload)}
          <button onClick={() => reload()} className="btn-ghost p-2 rounded-lg" title="Refresh">
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          </button>
          <button
            onClick={() => setOpen(o => !o)}
            className="flex items-center gap-2 bg-amber-500 hover:bg-amber-400 text-gray-950 px-4 py-2 rounded-lg font-medium text-sm"
          >
            <Plus size={16} /> {open ? 'Cancel' : 'New'}
          </button>
        </div>
      </div>

      {open && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {p.fields.map(f => (
              <div key={f.key}>
                <label className="text-xs text-gray-400 uppercase tracking-wide">
                  {f.label}{f.required && <span className="text-red-400"> *</span>}
                </label>
                {f.type === 'bool' ? (
                  <select
                    value={form[f.key] === true ? 'true' : form[f.key] === false ? 'false' : ''}
                    onChange={e => setForm({ ...form, [f.key]: e.target.value === 'true' })}
                    className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm text-white mt-1"
                  >
                    <option value="">—</option>
                    <option value="true">Yes</option>
                    <option value="false">No</option>
                  </select>
                ) : f.type === 'select' ? (
                  <select
                    value={form[f.key] ?? ''}
                    onChange={e => setForm({ ...form, [f.key]: e.target.value })}
                    className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm text-white mt-1"
                  >
                    <option value="">—</option>
                    {(f.options || []).map(o => <option key={o} value={o}>{o}</option>)}
                  </select>
                ) : (
                  <input
                    type={f.type === 'number' ? 'number' : 'text'}
                    value={form[f.key] ?? ''}
                    placeholder={f.placeholder}
                    onChange={e => setForm({ ...form, [f.key]: e.target.value })}
                    className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm text-white mt-1"
                  />
                )}
              </div>
            ))}
          </div>
          {error && <div className="text-sm text-red-400">{error}</div>}
          <button
            onClick={submit}
            disabled={creating}
            className="bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-gray-950 px-4 py-1.5 rounded font-medium text-sm"
          >
            {creating ? 'Saving…' : 'Save'}
          </button>
        </div>
      )}

      <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-950 text-gray-400 text-xs uppercase tracking-wide">
            <tr>
              {p.columns.map(c => <th key={c.key} className="text-left px-4 py-2.5">{c.label}</th>)}
              {p.remove && <th className="px-4 py-2.5"></th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {(data || []).map((row: any) => (
              <tr key={row.id} className="hover:bg-gray-800/40">
                {p.columns.map(c => (
                  <td key={c.key} className="px-4 py-2.5 text-gray-200">
                    {c.format ? c.format(row[c.key]) : String(row[c.key] ?? '—')}
                  </td>
                ))}
                {p.remove && (
                  <td className="px-4 py-2.5 text-right">
                    <button
                      onClick={async () => { await doRemove(row.id); reload() }}
                      className="text-gray-500 hover:text-red-400"
                      title="Delete"
                    >
                      <Trash2 size={14} />
                    </button>
                  </td>
                )}
              </tr>
            ))}
            {!loading && (!data || data.length === 0) && (
              <tr><td colSpan={p.columns.length + 1} className="px-4 py-8 text-center text-gray-500">
                No records yet.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
