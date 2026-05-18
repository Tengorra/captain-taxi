import { useState, useMemo, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApi } from '../hooks/useApi'
import { api } from '../lib/api'
import { CheckCircle, XCircle, UserPlus, Upload } from 'lucide-react'
import clsx from 'clsx'

const TABS = ['SEARCH DRIVERS', 'ADD NEW DRIVER'] as const
type Tab = typeof TABS[number]

const PAGE_SIZE = 20

export default function Drivers() {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<Tab>('SEARCH DRIVERS')
  const [page, setPage] = useState(1)

  const [refId, setRefId]       = useState('')
  const [nameQ, setNameQ]       = useState('')
  const [phoneQ, setPhoneQ]     = useState('')
  const [plateQ, setPlateQ]     = useState('')
  const [statusF, setStatusF]   = useState('')
  const [activeF, setActiveF]   = useState('')
  const [sortBy, setSortBy]     = useState('name')

  const [applied, setApplied] = useState({
    refId: '', name: '', phone: '', plate: '', status: '', active: '', sort: 'name',
  })

  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<{ success: number; failed: number; dupes: number } | null>(null)
  const [importError, setImportError] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [newDriver, setNewDriver] = useState({
    phone: '', vehicle_make: '', vehicle_model: '', vehicle_plate: '',
    status: 'pending', driver_type: 'regular', city: 'saskatoon',
    first_name: '', last_name: '', aka: '', address: '',
    email: '', mobile_phone: '', other_phone: '', sex: 'male',
    badge_number: '', badge_expiry: '', badge_type: 'hackney',
    licence_number: '', licence_expiry: '', tax_number: '',
    commission_pct: '30', payment_on: 'sunday', payment_type: 'cash',
    bank_name: '', bank_account_number: '', sort_code: '', notes: '',
  })
  const [addLoading, setAddLoading] = useState(false)
  const [addError, setAddError]     = useState('')
  const [addSuccess, setAddSuccess] = useState(false)

  const { data: allDrivers, loading } = useApi(
    () => api.listDrivers({
      search: applied.name || applied.phone || undefined,
      status: applied.status || undefined,
    }),
    [applied]
  )

  const filtered = useMemo(() => {
    if (!allDrivers) return []
    let r = [...allDrivers]
    if (applied.refId) {
      const q = applied.refId.toLowerCase()
      r = r.filter(d =>
        d.id.toLowerCase().includes(q) ||
        (d.icabbi_ref || '').toLowerCase().includes(q) ||
        (d.icabbi_driver_id || '').toLowerCase().includes(q)
      )
    }
    if (applied.plate)
      r = r.filter(d =>
        d.vehicle_plate?.toLowerCase().includes(applied.plate.toLowerCase()) ||
        d.vehicle_ref?.toLowerCase().includes(applied.plate.toLowerCase())
      )
    if (applied.active === 'active')
      r = r.filter(d => d.is_active_flag === true || ['active', 'on_trip'].includes(d.status))
    else if (applied.active === 'inactive')
      r = r.filter(d => !(d.is_active_flag === true || ['active', 'on_trip'].includes(d.status)))
    if (applied.sort === 'id')
      r.sort((a, b) => (a.icabbi_ref || a.id).localeCompare(b.icabbi_ref || b.id))
    else
      r.sort((a, b) => a.name.localeCompare(b.name))
    return r
  }, [allDrivers, applied])

  const total      = filtered.length
  const totalPages = Math.ceil(total / PAGE_SIZE)
  const paged      = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  const handleSearch = () => {
    setApplied({ refId, name: nameQ, phone: phoneQ, plate: plateQ, status: statusF, active: activeF, sort: sortBy })
    setPage(1)
  }

  const handleImportCSV = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setImporting(true)
    setImportResult(null)
    setImportError('')

    try {
      const text = await file.text()

      // Tolerate \r\n line endings, but DO NOT trim away blank cells inside
      // quoted multi-line values. We split on real line boundaries first.
      const allLines = text.replace(/\r\n/g, '\n').split('\n')
      if (allLines.length < 2) {
        setImportError('CSV file is empty or has no data rows.')
        setImporting(false)
        return
      }

      // Re-join lines that contain unbalanced quotes (multi-line quoted notes).
      const lines: string[] = []
      let buf = ''
      let openQuotes = 0
      for (const raw of allLines) {
        buf = buf ? buf + '\n' + raw : raw
        for (const ch of raw) if (ch === '"') openQuotes++
        if (openQuotes % 2 === 0) {
          if (buf.trim()) lines.push(buf)
          buf = ''
          openQuotes = 0
        }
      }
      if (buf.trim()) lines.push(buf)

      const parseRow = (line: string): string[] => {
        const result: string[] = []
        let current = ''
        let inQuotes = false
        for (let i = 0; i < line.length; i++) {
          const ch = line[i]
          if (ch === '"') {
            if (inQuotes && line[i + 1] === '"') { current += '"'; i++ }
            else inQuotes = !inQuotes
          } else if (ch === ',' && !inQuotes) {
            result.push(current)
            current = ''
          } else {
            current += ch
          }
        }
        result.push(current)
        return result.map(s => s.trim())
      }

      // iCabbi exports DD/MM/YYYY HH:mm. Return YYYY-MM-DD or '' for invalid/1969.
      const parseDate = (raw: string): string => {
        if (!raw) return ''
        if (raw.includes('1969')) return ''  // iCabbi's "null date" sentinel
        const m = raw.match(/(\d{1,2})\/(\d{1,2})\/(\d{4})/)
        if (!m) return ''
        return `${m[3]}-${m[2].padStart(2, '0')}-${m[1].padStart(2, '0')}`
      }

      const parseDateTime = (raw: string): string => {
        if (!raw) return ''
        if (raw.includes('1969')) return ''
        const m = raw.match(/(\d{1,2})\/(\d{1,2})\/(\d{4})(?:\s+(\d{1,2}):(\d{2}))?/)
        if (!m) return ''
        const d = `${m[3]}-${m[2].padStart(2, '0')}-${m[1].padStart(2, '0')}`
        const t = m[4] ? `T${m[4].padStart(2, '0')}:${m[5]}:00` : 'T00:00:00'
        return d + t
      }

      // iCabbi sometimes exports long phone numbers as scientific notation
      // (e.g. "1.31445E+12" instead of "13144500000000"). Best-effort recover
      // — Excel rounds the trailing digits, so this is imperfect but better
      // than dropping the value entirely.
      const normalizePhone = (raw: string): string => {
        if (!raw) return ''
        const cleaned = raw.replace(/\s+/g, '')
        if (/^\d{6,}$/.test(cleaned)) return cleaned
        if (/^[\d.]+e[+\-]?\d+$/i.test(cleaned)) {
          const n = Number(cleaned)
          if (Number.isFinite(n)) return Math.round(n).toString()
        }
        return cleaned
      }

      const toBool = (raw: string): boolean => raw === '1' || raw.toLowerCase() === 'yes' || raw.toLowerCase() === 'true'
      const toIntOrUndef = (raw: string): number | undefined => {
        if (!raw) return undefined
        const n = parseInt(raw, 10)
        return Number.isFinite(n) ? n : undefined
      }

      const headers = parseRow(lines[0]).map(h => h.replace(/"/g, '').trim())
      const headerIdx = new Map<string, number>()
      headers.forEach((h, i) => headerIdx.set(h, i))
      // Some iCabbi exports have a leading blank header column. We allow
      // lookup by exact column name only — the user's pasted file matches.

      // Columns we already first-class on the backend. Everything NOT in this
      // set gets dumped into `icabbi_config` as a JSON blob (still queryable
      // via SQL, but kept out of the main schema).
      const FIRST_CLASSED = new Set<string>([
        'ACTIVE', 'DRIVER', 'REF', 'Vehicle', 'PIN',
        'FIRST NAME', 'LAST NAME', 'AKA',
        'Phone', 'MOBILE', 'Email', 'Address',
        'START DATE', 'GENDER',
        'BADGE/PSV', 'PSV EXPIRY', 'BADGE TYPE', 'IMEI/UDID',
        'LICENCE', 'Header.licence_expiry', 'SCHOOL BADGE EXPIRY', 'NI NUMBER',
        'VERSION', 'LEGACY VERSION', 'INSTALLED LEGACY VERSION',
        'PHONE OS', 'PHONE OS VERSION', 'PHONE MANUFACTURER', 'PHONE MODEL',
        'DELETED', 'LAST UPDATED', 'LAST ACTIVE',
        'FREQUENCY', 'FREQUENCY DAY', 'PAYMENT TYPE', 'PAYMENT PERIOD',
        'PAYMENT TERMS', 'LAST PAYMENT', 'OUTPUT PREFERENCE',
        'NOTES', 'Profile Photo', 'PHONE LOCKED', 'SI ID',
      ])

      let success = 0
      let failed = 0
      let skippedDupe = 0
      let skippedBlank = 0
      const errors: string[] = []

      for (let i = 1; i < lines.length; i++) {
        const cols = parseRow(lines[i])
        const get = (name: string): string => {
          const idx = headerIdx.get(name)
          if (idx === undefined) return ''
          return (cols[idx] || '').replace(/^"|"$/g, '').trim()
        }

        const firstName = get('FIRST NAME')
        const lastName  = get('LAST NAME')
        const refNum    = get('REF')
        const driverId  = get('DRIVER')

        // Skip rows that are completely empty (no ref, no name, no driver id).
        // Placeholder "_copy" rows in iCabbi exports look like this.
        if (!firstName && !lastName && !refNum && !driverId) {
          skippedBlank++
          continue
        }

        // Build the icabbi_config blob from every "extra" column.
        const icabbiConfig: Record<string, string> = {}
        headers.forEach((h, idx) => {
          if (!h || FIRST_CLASSED.has(h)) return
          const v = (cols[idx] || '').trim()
          if (v) icabbiConfig[h] = v
        })

        const address = get('Address')
        const cityGuess = address.toLowerCase().includes('regina') ? 'regina' : 'saskatoon'

        const isActiveFlag = toBool(get('ACTIVE'))
        const isDeleted    = toBool(get('DELETED'))
        // Map iCabbi flags → existing dashboard status vocabulary
        let importStatus: 'active' | 'suspended' | 'inactive' = 'inactive'
        if (isDeleted) importStatus = 'suspended'
        else if (isActiveFlag) importStatus = 'active'

        const gender = get('GENDER')

        try {
          await api.createDriver({
            // Identity
            first_name:  firstName || undefined,
            last_name:   lastName  || undefined,
            aka:         get('AKA') || undefined,
            gender:      gender || undefined,
            address:     address || undefined,
            email:       get('Email') || undefined,
            phone:       normalizePhone(get('Phone')) || undefined,
            mobile:      normalizePhone(get('MOBILE')) || undefined,
            city:        cityGuess,
            // Status
            status:      importStatus,
            is_active_flag: isActiveFlag,
            is_deleted:     isDeleted,
            // iCabbi linkage
            icabbi_driver_id: driverId || undefined,
            icabbi_ref:       refNum   || undefined,
            vehicle_ref:      get('Vehicle') || undefined,
            start_date:       parseDateTime(get('START DATE')) || undefined,
            // Licensing
            badge_number:        get('BADGE/PSV') || undefined,
            badge_expiry:        parseDate(get('PSV EXPIRY')) || undefined,
            badge_type:          get('BADGE TYPE') || undefined,
            school_badge_expiry: parseDate(get('SCHOOL BADGE EXPIRY')) || undefined,
            licence_number:      get('LICENCE') || undefined,
            licence_expiry:      parseDate(get('Header.licence_expiry')) || undefined,
            ni_number:           get('NI NUMBER') || undefined,
            // Device / app
            imei_udid:                get('IMEI/UDID') || undefined,
            app_version:              get('VERSION') || undefined,
            legacy_version:           get('LEGACY VERSION') || undefined,
            installed_legacy_version: get('INSTALLED LEGACY VERSION') || undefined,
            phone_os:                 get('PHONE OS') || undefined,
            phone_os_version:         get('PHONE OS VERSION') || undefined,
            phone_manufacturer:       get('PHONE MANUFACTURER') || undefined,
            phone_model:              get('PHONE MODEL') || undefined,
            phone_locked:             get('PHONE LOCKED').toUpperCase() === 'YES',
            profile_photo:            get('Profile Photo') || undefined,
            // Activity
            last_updated_at: parseDateTime(get('LAST UPDATED')) || undefined,
            last_active_at:  parseDateTime(get('LAST ACTIVE')) || undefined,
            // Payments
            payment_type:      get('PAYMENT TYPE') ? get('PAYMENT TYPE').toLowerCase() : undefined,
            payment_period:    toIntOrUndef(get('PAYMENT PERIOD')),
            payment_terms:     toIntOrUndef(get('PAYMENT TERMS')),
            last_payment_at:   parseDateTime(get('LAST PAYMENT')) || undefined,
            output_preference: get('OUTPUT PREFERENCE') || undefined,
            frequency:         get('FREQUENCY') || undefined,
            frequency_day:     toIntOrUndef(get('FREQUENCY DAY')),
            si_id:             get('SI ID') || undefined,
            commission_rate:   0.30,
            driver_type:       'regular',
            notes:             get('NOTES') || undefined,
            // Everything else
            icabbi_config: Object.keys(icabbiConfig).length ? icabbiConfig : undefined,
          })
          success++
        } catch (err: unknown) {
          const msg = err instanceof Error ? err.message : String(err)
          if (msg.includes('409') || msg.toLowerCase().includes('already exists')) {
            skippedDupe++
          } else {
            errors.push(`Row ${i} (REF ${refNum || '—'}): ${firstName} ${lastName} — ${msg}`)
            failed++
          }
        }
      }

      if (errors.length > 0) console.warn('Import errors:', errors)
      if (skippedBlank > 0) console.info(`Skipped ${skippedBlank} blank placeholder rows`)
      setImportResult({ success, failed, dupes: skippedDupe })
    } catch (err: unknown) {
      setImportError(err instanceof Error ? err.message : 'Import failed. Please check the CSV file.')
    } finally {
      setImporting(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleAddDriver = async () => {
    if (!newDriver.first_name.trim() || !newDriver.last_name.trim() || !newDriver.phone.trim()) {
      setAddError('First name, last name, and phone are required.')
      return
    }
    setAddLoading(true)
    setAddError('')
    setAddSuccess(false)
    try {
      await api.createDriver({
        first_name:      newDriver.first_name,
        last_name:       newDriver.last_name,
        email:           newDriver.email,
        phone:           newDriver.phone,
        city:            newDriver.city,
        address:         newDriver.address || undefined,
        aka:             newDriver.aka || undefined,
        sex:             newDriver.sex || undefined,
        vehicle_make:    newDriver.vehicle_make || undefined,
        vehicle_model:   newDriver.vehicle_model || undefined,
        vehicle_plate:   newDriver.vehicle_plate || undefined,
        badge_number:    newDriver.badge_number || undefined,
        badge_expiry:    newDriver.badge_expiry || undefined,
        badge_type:      newDriver.badge_type || undefined,
        licence_number:  newDriver.licence_number || undefined,
        licence_expiry:  newDriver.licence_expiry || undefined,
        notes:           newDriver.notes || undefined,
        commission_rate: newDriver.commission_pct ? Number(newDriver.commission_pct) / 100 : undefined,
        driver_type:     newDriver.driver_type || undefined,
        payment_type:    newDriver.payment_type || undefined,
      })
      setAddSuccess(true)
      setNewDriver({
        phone: '', vehicle_make: '', vehicle_model: '', vehicle_plate: '',
        status: 'pending', driver_type: 'regular', city: 'saskatoon',
        first_name: '', last_name: '', aka: '', address: '',
        email: '', mobile_phone: '', other_phone: '', sex: 'male',
        badge_number: '', badge_expiry: '', badge_type: 'hackney',
        licence_number: '', licence_expiry: '', tax_number: '',
        commission_pct: '30', payment_on: 'sunday', payment_type: 'cash',
        bank_name: '', bank_account_number: '', sort_code: '', notes: '',
      })
    } catch (e: any) {
      setAddError(e.message || 'Failed to add driver.')
    } finally {
      setAddLoading(false)
    }
  }

  function AddSection({ title, children }: { title: string; children: React.ReactNode }) {
    return (
      <div className="overflow-hidden rounded-lg border border-gray-700">
        <div className="bg-gray-800 px-4 py-2.5 border-b border-gray-700">
          <h3 className="text-xs font-semibold text-gray-400 tracking-widest uppercase">{title}</h3>
        </div>
        <div className="bg-gray-900/60 p-4 space-y-2.5">{children}</div>
      </div>
    )
  }

  function AddField({ label, children }: { label: string; children: React.ReactNode }) {
    return (
      <div className="grid items-center gap-3" style={{ gridTemplateColumns: '136px 1fr' }}>
        <label className="text-xs text-gray-400 tracking-wide text-right">{label}</label>
        <div>{children}</div>
      </div>
    )
  }

  const isActive = (status: string) => ['active', 'on_trip'].includes(status)

  // Display a YYYY-MM-DD or ISO datetime as DD/MM/YYYY (iCabbi style)
  const fmtDate = (s?: string): string => {
    if (!s) return '—'
    const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/)
    if (!m) return s
    return `${m[3]}/${m[2]}/${m[1]}`
  }

  const pageRange = () => {
    const start = Math.max(1, Math.min(page - 2, totalPages - 4))
    const end   = Math.min(totalPages, start + 4)
    return Array.from({ length: end - start + 1 }, (_, i) => start + i)
  }

  return (
    <div>
      <div className="flex border-b border-gray-700">
        {TABS.map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={clsx(
              'px-5 py-2.5 text-xs font-semibold tracking-widest uppercase transition-colors',
              activeTab === tab
                ? 'bg-gray-800 text-white border-b-2 border-amber-500'
                : 'text-gray-500 hover:text-gray-200 hover:bg-gray-800/50'
            )}
          >
            {tab}
          </button>
        ))}
      </div>

      {activeTab === 'SEARCH DRIVERS' && (
        <div className="card rounded-tl-none">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3 mb-4">
            {[
              { label: 'REF/ID',  value: refId,   onChange: setRefId },
              { label: 'NAME',    value: nameQ,   onChange: setNameQ },
              { label: 'PHONE',   value: phoneQ,  onChange: setPhoneQ },
              { label: 'PLATE',   value: plateQ,  onChange: setPlateQ },
            ].map(({ label, value, onChange }) => (
              <div key={label} className="flex items-center gap-2">
                <span className="text-xs text-gray-400 w-16 shrink-0 tracking-wide">{label}</span>
                <input
                  className="input flex-1 text-sm"
                  value={value}
                  onChange={e => onChange(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleSearch()}
                />
              </div>
            ))}
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-400 w-16 shrink-0 tracking-wide">STATUS</span>
              <select className="input flex-1 text-sm" value={statusF} onChange={e => setStatusF(e.target.value)}>
                <option value="">ALL</option>
                <option value="active">Active</option>
                <option value="on_trip">On Trip</option>
                <option value="offline">Offline</option>
                <option value="suspended">Suspended</option>
                <option value="pending">Pending</option>
              </select>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-400 w-16 shrink-0 tracking-wide">ACTIVE</span>
              <select className="input flex-1 text-sm" value={activeF} onChange={e => setActiveF(e.target.value)}>
                <option value="">ALL</option>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-400 w-16 shrink-0 tracking-wide">SORT</span>
              <select className="input flex-1 text-sm" value={sortBy} onChange={e => setSortBy(e.target.value)}>
                <option value="name">Name</option>
                <option value="id">Driver REF</option>
              </select>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
            <div className="flex items-center gap-3 flex-wrap">
              <label className={clsx(
                'flex items-center gap-2 px-5 py-2 text-xs rounded tracking-widest transition-colors',
                importing
                  ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
                  : 'bg-amber-600 hover:bg-amber-500 text-white cursor-pointer'
              )}>
                <Upload size={13} />
                {importing ? 'IMPORTING...' : 'IMPORT ICABBI CSV'}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv"
                  className="hidden"
                  onChange={handleImportCSV}
                  disabled={importing}
                />
              </label>
              {importing && (
                <span className="text-xs text-amber-400 animate-pulse">Processing drivers, please wait...</span>
              )}
              {importResult && !importing && (
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-emerald-400 font-semibold">{importResult.success} imported</span>
                  {importResult.dupes > 0 && (
                    <span className="text-amber-400 font-semibold">· {importResult.dupes} already existed</span>
                  )}
                  {importResult.failed > 0 && (
                    <span className="text-red-400 font-semibold">· {importResult.failed} failed (check console)</span>
                  )}
                </div>
              )}
              {importError && <span className="text-xs text-red-400">{importError}</span>}
            </div>
            <button onClick={handleSearch} className="btn-primary px-10 tracking-widest text-xs">
              SEARCH
            </button>
          </div>

          {!loading && (
            <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
              <p className="text-xs text-gray-400">
                Showing <span className="text-white font-medium">{total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1}</span> to <span className="text-white font-medium">{Math.min(page * PAGE_SIZE, total)}</span> of <span className="text-white font-medium">{total}</span> Driver(s)
              </p>
              {totalPages > 1 && (
                <div className="flex items-center gap-1 text-xs">
                  <button onClick={() => setPage(1)} disabled={page === 1} className="px-2 py-1 rounded bg-gray-700 text-gray-300 disabled:opacity-30">First</button>
                  <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="px-2 py-1 rounded bg-gray-700 text-gray-300 disabled:opacity-30">Prev</button>
                  {pageRange().map(p => (
                    <button key={p} onClick={() => setPage(p)} className={clsx('w-7 h-7 rounded font-semibold transition-colors', page === p ? 'bg-amber-500 text-black' : 'bg-gray-700 text-gray-300 hover:bg-gray-600')}>{p}</button>
                  ))}
                  {totalPages > 5 && page < totalPages - 2 && <span className="text-gray-600 px-1">...</span>}
                  <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages || totalPages === 0} className="px-2 py-1 rounded bg-gray-700 text-gray-300 disabled:opacity-30">Next</button>
                  <button onClick={() => setPage(totalPages)} disabled={page === totalPages || totalPages === 0} className="px-2 py-1 rounded bg-gray-700 text-gray-300 disabled:opacity-30">Last</button>
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
                <UserPlus size={28} className="mx-auto mb-2" />
                <p className="text-sm">No drivers found — adjust filters and search</p>
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-800/60 border-b border-gray-700">
                    {['REF', 'FIRST NAME', 'LAST NAME', 'MOBILE', 'BADGE/PSV', 'BADGE EXPIRY', 'LICENCE EXPIRY', 'VEHICLE', 'CITY', 'LAST ACTIVE', 'ACTIVE', 'EDIT'].map(col => (
                      <th key={col} className="text-left px-3 py-2.5 text-xs font-semibold text-gray-400 tracking-widest uppercase whitespace-nowrap border-r border-gray-700/50 last:border-0">{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800/60">
                  {paged.map(driver => {
                    const activeNow = driver.is_active_flag === true || isActive(driver.status)
                    return (
                      <tr key={driver.id} className="hover:bg-gray-800/40 transition-colors">
                        <td className="px-3 py-2.5 text-amber-300 font-mono text-xs whitespace-nowrap">{driver.icabbi_ref || driver.id.slice(0, 8).toUpperCase()}</td>
                        <td className="px-3 py-2.5 text-white font-medium whitespace-nowrap">{driver.first_name || driver.name?.split(' ')[0] || '—'}</td>
                        <td className="px-3 py-2.5 text-white font-medium whitespace-nowrap">{driver.last_name || driver.name?.split(' ').slice(1).join(' ') || '—'}</td>
                        <td className="px-3 py-2.5 text-gray-300 font-mono text-xs whitespace-nowrap">{driver.mobile || driver.phone || '—'}</td>
                        <td className="px-3 py-2.5 text-gray-300 text-xs whitespace-nowrap">{driver.badge_number || '—'}</td>
                        <td className="px-3 py-2.5 text-gray-400 text-xs whitespace-nowrap">{fmtDate(driver.badge_expiry)}</td>
                        <td className="px-3 py-2.5 text-gray-400 text-xs whitespace-nowrap">{fmtDate(driver.licence_expiry)}</td>
                        <td className="px-3 py-2.5 text-gray-300 text-xs whitespace-nowrap">{driver.vehicle_ref || driver.vehicle_plate || '—'}</td>
                        <td className="px-3 py-2.5 text-gray-500 text-xs whitespace-nowrap capitalize">{driver.city || '—'}</td>
                        <td className="px-3 py-2.5 text-gray-500 text-xs whitespace-nowrap">{fmtDate(driver.last_active_at)}</td>
                        <td className="px-3 py-2.5">
                          {activeNow ? <CheckCircle size={16} className="text-emerald-400" /> : <XCircle size={16} className="text-red-400/50" />}
                        </td>
                        <td className="px-3 py-2.5">
                          <button onClick={() => navigate(`/drivers/${driver.id}`)} className="px-3 py-1 text-xs bg-gray-700 hover:bg-gray-600 text-white rounded transition-colors tracking-wide">EDIT</button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {activeTab === 'ADD NEW DRIVER' && (
        <div className="space-y-4 max-w-5xl">
          {addSuccess && (
            <div className="p-3 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm">Driver added successfully.</div>
          )}
          {addError && (
            <div className="p-3 rounded bg-red-500/10 border border-red-500/20 text-red-400 text-sm">{addError}</div>
          )}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <AddSection title="Details">
              <AddField label="PHONE *"><input className="input w-full text-sm" value={newDriver.phone} onChange={e => setNewDriver(d => ({ ...d, phone: e.target.value }))} /></AddField>
              <AddField label="VEHICLE MODEL"><input className="input w-full text-sm" value={newDriver.vehicle_model} onChange={e => setNewDriver(d => ({ ...d, vehicle_model: e.target.value }))} /></AddField>
              <AddField label="VEHICLE PLATE"><input className="input w-full text-sm uppercase" value={newDriver.vehicle_plate} onChange={e => setNewDriver(d => ({ ...d, vehicle_plate: e.target.value }))} /></AddField>
              <AddField label="STATUS">
                <select className="input w-full text-sm" value={newDriver.status} onChange={e => setNewDriver(d => ({ ...d, status: e.target.value }))}>
                  <option value="pending">PENDING / ONBOARDING</option>
                  <option value="active">ACTIVE</option>
                  <option value="offline">INACTIVE</option>
                </select>
              </AddField>
              <AddField label="DRIVER TYPE">
                <select className="input w-full text-sm" value={newDriver.driver_type} onChange={e => setNewDriver(d => ({ ...d, driver_type: e.target.value }))}>
                  <option value="regular">Regular Driver</option>
                  <option value="wheelchair">Wheelchair</option>
                  <option value="executive">Executive</option>
                  <option value="school">School</option>
                </select>
              </AddField>
              <AddField label="CITY">
                <select className="input w-full text-sm" value={newDriver.city} onChange={e => setNewDriver(d => ({ ...d, city: e.target.value }))}>
                  <option value="saskatoon">Captain Taxi Saskatoon</option>
                  <option value="regina">Captain Taxi Regina</option>
                </select>
              </AddField>
            </AddSection>
            <AddSection title="Personal">
              <AddField label="FIRST NAME *"><input className="input w-full text-sm" value={newDriver.first_name} onChange={e => setNewDriver(d => ({ ...d, first_name: e.target.value }))} /></AddField>
              <AddField label="LAST NAME *"><input className="input w-full text-sm" value={newDriver.last_name} onChange={e => setNewDriver(d => ({ ...d, last_name: e.target.value }))} /></AddField>
              <AddField label="A.K.A."><input className="input w-full text-sm" value={newDriver.aka} onChange={e => setNewDriver(d => ({ ...d, aka: e.target.value }))} /></AddField>
              <AddField label="ADDRESS"><input className="input w-full text-sm" value={newDriver.address} onChange={e => setNewDriver(d => ({ ...d, address: e.target.value }))} /></AddField>
              <AddField label="EMAIL"><input className="input w-full text-sm" type="email" value={newDriver.email} onChange={e => setNewDriver(d => ({ ...d, email: e.target.value }))} /></AddField>
              <AddField label="MOBILE PHONE"><input className="input w-full text-sm" value={newDriver.mobile_phone} onChange={e => setNewDriver(d => ({ ...d, mobile_phone: e.target.value }))} /></AddField>
              <AddField label="OTHER PHONE"><input className="input w-full text-sm" value={newDriver.other_phone} onChange={e => setNewDriver(d => ({ ...d, other_phone: e.target.value }))} /></AddField>
              <AddField label="SEX">
                <select className="input w-full text-sm" value={newDriver.sex} onChange={e => setNewDriver(d => ({ ...d, sex: e.target.value }))}>
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                  <option value="other">Other / Prefer not to say</option>
                </select>
              </AddField>
            </AddSection>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <AddSection title="Licensing">
              <AddField label="BADGE"><input className="input w-full text-sm" placeholder="Badge / PSV number" value={newDriver.badge_number} onChange={e => setNewDriver(d => ({ ...d, badge_number: e.target.value }))} /></AddField>
              <AddField label="BADGE EXPIRY"><input className="input w-full text-sm" type="date" value={newDriver.badge_expiry} onChange={e => setNewDriver(d => ({ ...d, badge_expiry: e.target.value }))} /></AddField>
              <AddField label="BADGE TYPE">
                <select className="input w-full text-sm" value={newDriver.badge_type} onChange={e => setNewDriver(d => ({ ...d, badge_type: e.target.value }))}>
                  <option value="hackney">Hackney</option>
                  <option value="metropolitan">Metropolitan</option>
                  <option value="provincial">Provincial</option>
                </select>
              </AddField>
              <AddField label="LICENCE"><input className="input w-full text-sm" placeholder="Driver's licence number" value={newDriver.licence_number} onChange={e => setNewDriver(d => ({ ...d, licence_number: e.target.value }))} /></AddField>
              <AddField label="LICENCE EXPIRY"><input className="input w-full text-sm" type="date" value={newDriver.licence_expiry} onChange={e => setNewDriver(d => ({ ...d, licence_expiry: e.target.value }))} /></AddField>
              <AddField label="TAX NUMBER"><input className="input w-full text-sm" value={newDriver.tax_number} onChange={e => setNewDriver(d => ({ ...d, tax_number: e.target.value }))} /></AddField>
            </AddSection>
            <AddSection title="Payments">
              <AddField label="COMMISSION (%)"><input className="input w-full text-sm" type="number" min="0" max="100" value={newDriver.commission_pct} onChange={e => setNewDriver(d => ({ ...d, commission_pct: e.target.value }))} /></AddField>
              <AddField label="PAYMENT ON">
                <select className="input w-full text-sm" value={newDriver.payment_on} onChange={e => setNewDriver(d => ({ ...d, payment_on: e.target.value }))}>
                  {['monday','tuesday','wednesday','thursday','friday','saturday','sunday'].map(d => (
                    <option key={d} value={d}>{d.charAt(0).toUpperCase() + d.slice(1)}</option>
                  ))}
                </select>
              </AddField>
              <AddField label="PAYMENT TYPE">
                <select className="input w-full text-sm" value={newDriver.payment_type} onChange={e => setNewDriver(d => ({ ...d, payment_type: e.target.value }))}>
                  <option value="cash">Cash</option>
                  <option value="bank_transfer">Bank Transfer</option>
                  <option value="card">Card</option>
                </select>
              </AddField>
              <AddField label="BANK NAME"><input className="input w-full text-sm" value={newDriver.bank_name} onChange={e => setNewDriver(d => ({ ...d, bank_name: e.target.value }))} /></AddField>
              <AddField label="ACCOUNT NUMBER"><input className="input w-full text-sm" value={newDriver.bank_account_number} onChange={e => setNewDriver(d => ({ ...d, bank_account_number: e.target.value }))} /></AddField>
              <AddField label="SORT CODE"><input className="input w-full text-sm" value={newDriver.sort_code} onChange={e => setNewDriver(d => ({ ...d, sort_code: e.target.value }))} /></AddField>
            </AddSection>
          </div>
          <div className="flex gap-3">
            <button onClick={handleAddDriver} disabled={addLoading} className="btn-primary px-8 tracking-widest text-xs">
              {addLoading ? 'ADDING...' : 'ADD DRIVER'}
            </button>
            <button onClick={() => { setActiveTab('SEARCH DRIVERS'); setAddError(''); setAddSuccess(false) }} className="px-5 py-2 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 rounded transition-colors tracking-widest">
              CANCEL
            </button>
          </div>
        </div>
      )}
    </div>
  )
}