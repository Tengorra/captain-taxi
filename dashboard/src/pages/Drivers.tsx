import { useState, useMemo, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApi } from '../hooks/useApi'
import { api } from '../lib/api'
import {
  CheckCircle, XCircle, UserPlus, Upload, ChevronLeft, ChevronRight,
  FileText, Trash2,
} from 'lucide-react'
import clsx from 'clsx'

const SITES = [
  { code: 'CTS', name: 'Captain Taxi Saskatoon' },
  { code: 'CTR', name: 'Captain Taxi Regina' },
] as const

const FILE_TYPES = [
  { key: 'police_disclosure', label: 'Police Disclosure' },
  { key: 'agreement',          label: 'Agreement' },
  { key: 'proof_of_address',   label: 'Proof of Address' },
  { key: 'photo_id',           label: 'Photo ID' },
  { key: 'licence_photo',      label: 'Licence Photo' },
  { key: 'licence_paper',      label: 'Licence Paper' },
  { key: 'pco_licence',        label: 'PCO Licence' },
  { key: 'insurance',          label: 'Insurance' },
] as const

const WIZARD_STEPS = [
  { key: 'personal',  label: 'Personal' },
  { key: 'licensing', label: 'Licensing' },
  { key: 'payments',  label: 'Payments / VAT' },
  { key: 'documents', label: 'Documents' },
  { key: 'sites',     label: 'Sites' },
] as const
type WizardStep = typeof WIZARD_STEPS[number]['key']

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

  const [wizardStep, setWizardStep] = useState<WizardStep>('personal')
  const [newDriver, setNewDriver] = useState({
    // Personal
    first_name: '', last_name: '', aka: '', sex: 'male', ethnicity: '',
    address: '', email: '', phone: '', mobile_phone: '', other_phone: '',
    city: 'saskatoon', driver_type: 'regular', status: 'pending',
    transporter: false, login_username: '', login_password: '',
    // Licensing
    badge_number: '', badge_expiry: '', badge_type: 'hackney',
    school_badge_expiry: '',
    licence_number: '', licence_expiry: '', tax_number: '',
    pvg_disclosure: '',
    // Vehicle (kept for quick-link to a vehicle row on create)
    vehicle_ref: '', vehicle_make: '', vehicle_model: '', vehicle_plate: '',
    // Attributes
    attr_pets: false, attr_uniformed: false, attr_topman: false,
    attr_accept_discount: true, attr_accept_account: true,
    attr_accept_fixed_fares: true, attr_accept_cash_work: true,
    // Device extras
    phone_assist: false,
    // Payments / VAT
    commission_pct: '30', payment_on_day: 'sunday', payment_type: 'cash',
    frequency: '', payment_period: '', payment_terms: '', output_preference: '',
    invoice_footer: '', shift_reporting: false,
    distribution: 'POST', apply_vat: false, vat_rate: '',
    exclude_booking_fee: false, auto_post: 'SYSTEM_DEFAULT',
    bank_payment_ref: '', use_sepa: false,
    bank_name: '', bank_account_name: '', bank_account_number: '', sort_code: '',
    // Custom fields
    police_record: '', police_record_2: '',
    // Breathalyser
    breathalyser_enabled: false,
    // Fatigue
    fatigue_max_work_hours: '0', fatigue_min_rest_hours: '0',
    fatigue_exceed_job_pct: '0', fatigue_send_alert_pct: '0',
    // Notes
    notes: '',
  })
  // Site assignments (multi-select, one is primary)
  const [siteSel, setSiteSel] = useState<Record<string, { assigned: boolean; primary: boolean }>>(
    Object.fromEntries(SITES.map(s => [s.code, { assigned: false, primary: false }]))
  )
  // Documents queued for upload (file is held until driver is created)
  const [docQueue, setDocQueue] = useState<Record<string, File | null>>(
    Object.fromEntries(FILE_TYPES.map(t => [t.key, null]))
  )
  const [addLoading, setAddLoading] = useState(false)
  const [addError, setAddError]     = useState('')
  const [addSuccess, setAddSuccess] = useState(false)
  const [docUploadStatus, setDocUploadStatus] = useState('')

  // Vehicle CSV import — separate button, parallel to the driver importer
  const [vehImporting, setVehImporting] = useState(false)
  const [vehImportResult, setVehImportResult] = useState<{ success: number; failed: number; dupes: number } | null>(null)
  const [vehImportError, setVehImportError] = useState('')
  const vehFileInputRef = useRef<HTMLInputElement>(null)

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

  const toIntOrUndef = (v: string): number | undefined => {
    if (!v) return undefined
    const n = parseInt(v, 10)
    return Number.isFinite(n) ? n : undefined
  }
  const toFloatOrUndef = (v: string): number | undefined => {
    if (!v) return undefined
    const n = parseFloat(v)
    return Number.isFinite(n) ? n : undefined
  }

  const handleAddDriver = async () => {
    if (!newDriver.first_name.trim() || !newDriver.last_name.trim() || !newDriver.phone.trim()) {
      setAddError('First name, last name, and phone are required.')
      setWizardStep('personal')
      return
    }
    setAddLoading(true)
    setAddError('')
    setAddSuccess(false)
    setDocUploadStatus('')
    try {
      const sites = SITES
        .filter(s => siteSel[s.code]?.assigned)
        .map(s => ({
          site_code: s.code,
          assigned: true,
          is_primary: !!siteSel[s.code]?.primary,
        }))

      const driver = await api.createDriver({
        // Personal
        first_name:    newDriver.first_name,
        last_name:     newDriver.last_name,
        aka:           newDriver.aka || undefined,
        sex:           newDriver.sex || undefined,
        ethnicity:     newDriver.ethnicity || undefined,
        address:       newDriver.address || undefined,
        email:         newDriver.email || undefined,
        phone:         newDriver.phone,
        mobile:        newDriver.mobile_phone || undefined,
        city:          newDriver.city,
        driver_type:   newDriver.driver_type || undefined,
        status:        newDriver.status || undefined,
        transporter:   newDriver.transporter,
        login_username: newDriver.login_username || undefined,
        login_password: newDriver.login_password || undefined,
        // Licensing
        badge_number:        newDriver.badge_number || undefined,
        badge_expiry:        newDriver.badge_expiry || undefined,
        badge_type:          newDriver.badge_type || undefined,
        school_badge_expiry: newDriver.school_badge_expiry || undefined,
        licence_number:      newDriver.licence_number || undefined,
        licence_expiry:      newDriver.licence_expiry || undefined,
        ni_number:           newDriver.tax_number || undefined,
        pvg_disclosure:      newDriver.pvg_disclosure || undefined,
        // Vehicle (quick-link)
        vehicle_ref:    newDriver.vehicle_ref   || undefined,
        vehicle_make:   newDriver.vehicle_make  || undefined,
        vehicle_model:  newDriver.vehicle_model || undefined,
        vehicle_plate:  newDriver.vehicle_plate || undefined,
        // Attributes
        attr_pets:               newDriver.attr_pets,
        attr_uniformed:          newDriver.attr_uniformed,
        attr_topman:             newDriver.attr_topman,
        attr_accept_discount:    newDriver.attr_accept_discount,
        attr_accept_account:     newDriver.attr_accept_account,
        attr_accept_fixed_fares: newDriver.attr_accept_fixed_fares,
        attr_accept_cash_work:   newDriver.attr_accept_cash_work,
        // Device extras
        phone_assist: newDriver.phone_assist,
        frequency: newDriver.frequency || undefined,
        // Payments / VAT
        commission_rate:     newDriver.commission_pct ? Number(newDriver.commission_pct) / 100 : undefined,
        payment_type:        newDriver.payment_type || undefined,
        payment_on_day:      newDriver.payment_on_day || undefined,
        payment_period:      toIntOrUndef(newDriver.payment_period),
        payment_terms:       toIntOrUndef(newDriver.payment_terms),
        output_preference:   newDriver.output_preference || undefined,
        invoice_footer:      newDriver.invoice_footer || undefined,
        shift_reporting:     newDriver.shift_reporting,
        distribution:        newDriver.distribution || undefined,
        apply_vat:           newDriver.apply_vat,
        vat_rate:            toFloatOrUndef(newDriver.vat_rate),
        exclude_booking_fee: newDriver.exclude_booking_fee,
        auto_post:           newDriver.auto_post || undefined,
        bank_payment_ref:    newDriver.bank_payment_ref || undefined,
        use_sepa:            newDriver.use_sepa,
        bank_name:           newDriver.bank_name || undefined,
        bank_account_name:   newDriver.bank_account_name || undefined,
        bank_account_number: newDriver.bank_account_number || undefined,
        sort_code:           newDriver.sort_code || undefined,
        // Custom fields
        police_record:   newDriver.police_record || undefined,
        police_record_2: newDriver.police_record_2 || undefined,
        // Breathalyser
        breathalyser_enabled: newDriver.breathalyser_enabled,
        // Fatigue
        fatigue_max_work_hours: toIntOrUndef(newDriver.fatigue_max_work_hours),
        fatigue_min_rest_hours: toIntOrUndef(newDriver.fatigue_min_rest_hours),
        fatigue_exceed_job_pct: toIntOrUndef(newDriver.fatigue_exceed_job_pct),
        fatigue_send_alert_pct: toIntOrUndef(newDriver.fatigue_send_alert_pct),
        // Sites
        sites: sites.length ? sites : undefined,
        // Notes
        notes: newDriver.notes || undefined,
      })

      // Upload any queued documents now that we have a driver ID. Failures
      // here don't roll back the driver — we just surface them.
      const queued = FILE_TYPES.filter(t => docQueue[t.key])
      if (queued.length && driver.id) {
        const failures: string[] = []
        for (const t of queued) {
          setDocUploadStatus(`Uploading ${t.label}…`)
          try { await api.uploadDriverFile(driver.id, t.key, docQueue[t.key] as File) }
          catch (e) { failures.push(`${t.label}: ${(e as Error).message}`) }
        }
        if (failures.length) {
          setDocUploadStatus(`Some uploads failed: ${failures.join('; ')}`)
        } else {
          setDocUploadStatus(`Uploaded ${queued.length} file(s).`)
        }
      }

      setAddSuccess(true)
      // Reset form
      setNewDriver({
        first_name: '', last_name: '', aka: '', sex: 'male', ethnicity: '',
        address: '', email: '', phone: '', mobile_phone: '', other_phone: '',
        city: 'saskatoon', driver_type: 'regular', status: 'pending',
        transporter: false, login_username: '', login_password: '',
        badge_number: '', badge_expiry: '', badge_type: 'hackney',
        school_badge_expiry: '',
        licence_number: '', licence_expiry: '', tax_number: '',
        pvg_disclosure: '',
        vehicle_ref: '', vehicle_make: '', vehicle_model: '', vehicle_plate: '',
        attr_pets: false, attr_uniformed: false, attr_topman: false,
        attr_accept_discount: true, attr_accept_account: true,
        attr_accept_fixed_fares: true, attr_accept_cash_work: true,
        phone_assist: false,
        commission_pct: '30', payment_on_day: 'sunday', payment_type: 'cash',
        frequency: '', payment_period: '', payment_terms: '', output_preference: '',
        invoice_footer: '', shift_reporting: false,
        distribution: 'POST', apply_vat: false, vat_rate: '',
        exclude_booking_fee: false, auto_post: 'SYSTEM_DEFAULT',
        bank_payment_ref: '', use_sepa: false,
        bank_name: '', bank_account_name: '', bank_account_number: '', sort_code: '',
        police_record: '', police_record_2: '',
        breathalyser_enabled: false,
        fatigue_max_work_hours: '0', fatigue_min_rest_hours: '0',
        fatigue_exceed_job_pct: '0', fatigue_send_alert_pct: '0',
        notes: '',
      })
      setSiteSel(Object.fromEntries(SITES.map(s => [s.code, { assigned: false, primary: false }])))
      setDocQueue(Object.fromEntries(FILE_TYPES.map(t => [t.key, null])))
      setWizardStep('personal')
    } catch (e: any) {
      setAddError(e.message || 'Failed to add driver.')
    } finally {
      setAddLoading(false)
    }
  }

  // ─────────────────────────── Vehicle CSV importer ──────────────────────────
  const handleImportVehicleCSV = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setVehImporting(true)
    setVehImportResult(null)
    setVehImportError('')

    try {
      const text = await file.text()
      const allLines = text.replace(/\r\n/g, '\n').split('\n')
      if (allLines.length < 2) {
        setVehImportError('CSV file is empty or has no data rows.')
        setVehImporting(false)
        return
      }
      // Re-join lines that contain unbalanced quotes
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
        let inQ = false
        for (let i = 0; i < line.length; i++) {
          const ch = line[i]
          if (ch === '"') {
            if (inQ && line[i + 1] === '"') { current += '"'; i++ }
            else inQ = !inQ
          } else if (ch === ',' && !inQ) {
            result.push(current); current = ''
          } else current += ch
        }
        result.push(current)
        return result.map(s => s.trim())
      }

      // iCabbi vehicle exports use MM/DD/YYYY HH:mm
      const parseDT = (raw: string): string => {
        if (!raw) return ''
        const m = raw.match(/(\d{1,2})\/(\d{1,2})\/(\d{4})(?:\s+(\d{1,2}):(\d{2}))?/)
        if (!m) return ''
        const d = `${m[3]}-${m[1].padStart(2, '0')}-${m[2].padStart(2, '0')}`
        const t = m[4] ? `T${m[4].padStart(2, '0')}:${m[5]}:00` : 'T00:00:00'
        return d + t
      }
      const toBool = (v: string): boolean =>
        v === '1' || v.toLowerCase() === 'yes' || v.toLowerCase() === 'true'
      const toIntOrU = (v: string): number | undefined => {
        if (!v) return undefined
        const n = parseInt(v, 10); return Number.isFinite(n) ? n : undefined
      }
      const toFloatOrU = (v: string): number | undefined => {
        if (!v) return undefined
        const n = parseFloat(v); return Number.isFinite(n) ? n : undefined
      }

      const headers = parseRow(lines[0]).map(h => h.replace(/"/g, '').trim())
      const idx = new Map<string, number>()
      headers.forEach((h, i) => idx.set(h, i))

      let success = 0, failed = 0, dupes = 0, blank = 0
      const errors: string[] = []

      for (let i = 1; i < lines.length; i++) {
        const cols = parseRow(lines[i])
        const g = (name: string): string => {
          const j = idx.get(name)
          if (j === undefined) return ''
          return (cols[j] || '').replace(/^"|"$/g, '').trim()
        }

        const ref = g('Vehicle Ref')
        if (!ref && !g('PLATE') && !g('Make')) { blank++; continue }

        try {
          await api.createVehicle({
            vehicle_ref:         ref || undefined,
            aka:                 g('AKA') || undefined,
            internal_system_id:  g('Internal System ID') || undefined,
            make:                g('Make') || undefined,
            model:               g('Model') || undefined,
            color:               g('Colour') || undefined,
            registration:        g('Registration') || undefined,
            plate:               g('PLATE') || g('Registration') || undefined,
            year:                toIntOrU(g('Year')),
            is_active:           toBool(g('Active')),
            is_deleted:          toBool(g('Deleted')),
            nct_mot_expiry:      parseDT(g('NCT/MOT Expiry')) || undefined,
            plate_expiry:        parseDT(g('Plate Expiry')) || undefined,
            insurance_expiry:    parseDT(g('Insurance Expiry')) || undefined,
            road_tax_expiry:     parseDT(g('Road Tax Expiry')) || undefined,
            council_compliance_expiry: parseDT(g('Council Compliance Expiry')) || undefined,
            hire_expiry:         parseDT(g('Hire Expiry')) || undefined,
            insurer:             g('Insurer') || undefined,
            insurance:           g('Insurance') || undefined,
            owner_driver:        toBool(g('Owner Driver')),
            device_identifier:   g('Device Identifier') || undefined,
            sensors:             g('Sensors') || undefined,
            payment_device:      g('Payment Device') || undefined,
            payment_version:     g('Payment Version') || undefined,
            light_control:       g('Light Control') || undefined,
            status_control:      g('Status Control') || undefined,
            vehicle_phone:       g('Vehicle Phone') || undefined,
            co2_emission:        toFloatOrU(g('Co2 Emission')),
            credit_card_payments: toBool(g('Credit Card Payments')),
            wifi:                toBool(g('Wi-Fi')),
            wheelchair:          g('Wheelchair') === 'YES',
            saloon:              g('Saloon') === 'YES',
            executive:           g('Executive') === 'YES',
            good_condition:      g('Good Condition') === 'YES',
            average_condition:   g('Average Condition') === 'YES',
            seater_4:            g('4 Seater') === 'YES',
            seater_5:            g('5 Seater') === 'YES',
            seater_6:            g('6 Seater') === 'YES',
            seater_7:            g('7 Seater') === 'YES',
            seater_8:            g('8 Seater') === 'YES',
            body_low_rider:      g('Low Rider') === 'YES',
            body_estate:         g('Estate') === 'YES',
            body_high_rider:     g('High Rider') === 'YES',
            body_sedan:          g('SEDAN') === 'YES',
            body_minivan:        g('MINIVAN') === 'YES',
            body_suv:            g('SUV') === 'YES',
            comments:            g('Comments') || undefined,
            driver_vehicle_ref:  ref || undefined,
          })
          success++
        } catch (err: unknown) {
          const msg = err instanceof Error ? err.message : String(err)
          if (msg.includes('409') || msg.toLowerCase().includes('already exists')) dupes++
          else { errors.push(`Row ${i} (REF ${ref || '—'}): ${msg}`); failed++ }
        }
      }
      if (errors.length) console.warn('Vehicle import errors:', errors)
      if (blank) console.info(`Skipped ${blank} blank vehicle rows`)
      setVehImportResult({ success, failed, dupes })
    } catch (err: unknown) {
      setVehImportError(err instanceof Error ? err.message : 'Vehicle import failed.')
    } finally {
      setVehImporting(false)
      if (vehFileInputRef.current) vehFileInputRef.current.value = ''
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

              <label className={clsx(
                'flex items-center gap-2 px-5 py-2 text-xs rounded tracking-widest transition-colors',
                vehImporting
                  ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
                  : 'bg-sky-600 hover:bg-sky-500 text-white cursor-pointer'
              )}>
                <Upload size={13} />
                {vehImporting ? 'IMPORTING...' : 'IMPORT VEHICLE CSV'}
                <input
                  ref={vehFileInputRef}
                  type="file"
                  accept=".csv"
                  className="hidden"
                  onChange={handleImportVehicleCSV}
                  disabled={vehImporting}
                />
              </label>
              {vehImporting && (
                <span className="text-xs text-sky-400 animate-pulse">Processing vehicles…</span>
              )}
              {vehImportResult && !vehImporting && (
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-emerald-400 font-semibold">{vehImportResult.success} imported</span>
                  {vehImportResult.dupes > 0 && (
                    <span className="text-amber-400 font-semibold">· {vehImportResult.dupes} already existed</span>
                  )}
                  {vehImportResult.failed > 0 && (
                    <span className="text-red-400 font-semibold">· {vehImportResult.failed} failed (check console)</span>
                  )}
                </div>
              )}
              {vehImportError && <span className="text-xs text-red-400">{vehImportError}</span>}
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
            <div className="p-3 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm">
              Driver added successfully. {docUploadStatus}
            </div>
          )}
          {addError && (
            <div className="p-3 rounded bg-red-500/10 border border-red-500/20 text-red-400 text-sm">{addError}</div>
          )}

          {/* Step indicator */}
          <div className="flex items-center gap-2 overflow-x-auto pb-2">
            {WIZARD_STEPS.map((s, i) => {
              const active = wizardStep === s.key
              const stepIndex = WIZARD_STEPS.findIndex(x => x.key === wizardStep)
              const past = i < stepIndex
              return (
                <button
                  key={s.key}
                  onClick={() => setWizardStep(s.key)}
                  className={clsx(
                    'flex items-center gap-2 px-3 py-1.5 rounded text-xs tracking-widest uppercase transition-colors whitespace-nowrap',
                    active ? 'bg-amber-500 text-black font-semibold'
                      : past ? 'bg-emerald-600/20 text-emerald-300 hover:bg-emerald-600/30'
                      : 'bg-gray-800 text-gray-500 hover:bg-gray-700'
                  )}
                >
                  <span className={clsx(
                    'w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold',
                    active ? 'bg-black/20 text-black'
                      : past ? 'bg-emerald-500 text-black'
                      : 'bg-gray-700 text-gray-400'
                  )}>{i + 1}</span>
                  {s.label}
                </button>
              )
            })}
          </div>

          {/* PERSONAL */}
          {wizardStep === 'personal' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <AddSection title="Details">
                <AddField label="DRIVER LOGIN"><input className="input w-full text-sm" placeholder="Username" value={newDriver.login_username} onChange={e => setNewDriver(d => ({ ...d, login_username: e.target.value }))} /></AddField>
                <AddField label="PASSWORD"><input className="input w-full text-sm" type="password" placeholder="Leave blank to skip" value={newDriver.login_password} onChange={e => setNewDriver(d => ({ ...d, login_password: e.target.value }))} /></AddField>
                <AddField label="PHONE *"><input className="input w-full text-sm" value={newDriver.phone} onChange={e => setNewDriver(d => ({ ...d, phone: e.target.value }))} /></AddField>
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
                <AddField label="TRANSPORTER">
                  <label className="inline-flex items-center gap-2 text-sm text-gray-300">
                    <input type="checkbox" checked={newDriver.transporter} onChange={e => setNewDriver(d => ({ ...d, transporter: e.target.checked }))} />
                    <span>Is a transporter</span>
                  </label>
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
                <AddField label="ETHNICITY"><input className="input w-full text-sm" value={newDriver.ethnicity} onChange={e => setNewDriver(d => ({ ...d, ethnicity: e.target.value }))} /></AddField>
              </AddSection>
            </div>
          )}

          {/* LICENSING */}
          {wizardStep === 'licensing' && (
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
                <AddField label="SCHOOL BADGE EXP."><input className="input w-full text-sm" type="date" value={newDriver.school_badge_expiry} onChange={e => setNewDriver(d => ({ ...d, school_badge_expiry: e.target.value }))} /></AddField>
                <AddField label="LICENCE"><input className="input w-full text-sm" placeholder="Driver's licence number" value={newDriver.licence_number} onChange={e => setNewDriver(d => ({ ...d, licence_number: e.target.value }))} /></AddField>
                <AddField label="LICENCE EXPIRY"><input className="input w-full text-sm" type="date" value={newDriver.licence_expiry} onChange={e => setNewDriver(d => ({ ...d, licence_expiry: e.target.value }))} /></AddField>
                <AddField label="TAX / NI NUMBER"><input className="input w-full text-sm" value={newDriver.tax_number} onChange={e => setNewDriver(d => ({ ...d, tax_number: e.target.value }))} /></AddField>
                <AddField label="PVG DISCLOSURE"><textarea className="input w-full text-sm" rows={2} value={newDriver.pvg_disclosure} onChange={e => setNewDriver(d => ({ ...d, pvg_disclosure: e.target.value }))} /></AddField>
              </AddSection>
              <AddSection title="Attributes">
                {[
                  ['attr_pets',               'Pets'],
                  ['attr_uniformed',          'Uniformed'],
                  ['attr_topman',             'Topman'],
                  ['attr_accept_discount',    'Accept Discount'],
                  ['attr_accept_account',     'Accept Account'],
                  ['attr_accept_fixed_fares', 'Accept Fixed Fares'],
                  ['attr_accept_cash_work',   'Accept Cash Work'],
                ].map(([key, label]) => (
                  <AddField key={key} label={label.toUpperCase()}>
                    <label className="inline-flex items-center gap-2 text-sm text-gray-300">
                      <input type="checkbox"
                        checked={!!(newDriver as any)[key]}
                        onChange={e => setNewDriver(d => ({ ...d, [key]: e.target.checked }))} />
                      <span>{(newDriver as any)[key] ? 'YES' : 'NO'}</span>
                    </label>
                  </AddField>
                ))}
              </AddSection>
              <AddSection title="Vehicle (Quick Link)">
                <AddField label="VEHICLE REF"><input className="input w-full text-sm" value={newDriver.vehicle_ref} onChange={e => setNewDriver(d => ({ ...d, vehicle_ref: e.target.value }))} /></AddField>
                <AddField label="MAKE"><input className="input w-full text-sm" value={newDriver.vehicle_make} onChange={e => setNewDriver(d => ({ ...d, vehicle_make: e.target.value }))} /></AddField>
                <AddField label="MODEL"><input className="input w-full text-sm" value={newDriver.vehicle_model} onChange={e => setNewDriver(d => ({ ...d, vehicle_model: e.target.value }))} /></AddField>
                <AddField label="PLATE"><input className="input w-full text-sm uppercase" value={newDriver.vehicle_plate} onChange={e => setNewDriver(d => ({ ...d, vehicle_plate: e.target.value }))} /></AddField>
              </AddSection>
              <AddSection title="Custom Fields">
                <AddField label="POLICE RECORD"><input className="input w-full text-sm" value={newDriver.police_record} onChange={e => setNewDriver(d => ({ ...d, police_record: e.target.value }))} /></AddField>
                <AddField label="POLICE RECORD 2"><input className="input w-full text-sm" value={newDriver.police_record_2} onChange={e => setNewDriver(d => ({ ...d, police_record_2: e.target.value }))} /></AddField>
                <AddField label="BREATHALYSER">
                  <label className="inline-flex items-center gap-2 text-sm text-gray-300">
                    <input type="checkbox" checked={newDriver.breathalyser_enabled} onChange={e => setNewDriver(d => ({ ...d, breathalyser_enabled: e.target.checked }))} />
                    <span>Breathalyser Enabled (primary site only)</span>
                  </label>
                </AddField>
                <AddField label="PHONE ASSIST">
                  <label className="inline-flex items-center gap-2 text-sm text-gray-300">
                    <input type="checkbox" checked={newDriver.phone_assist} onChange={e => setNewDriver(d => ({ ...d, phone_assist: e.target.checked }))} />
                    <span>{newDriver.phone_assist ? 'YES' : 'NO'}</span>
                  </label>
                </AddField>
              </AddSection>
            </div>
          )}

          {/* PAYMENTS / VAT */}
          {wizardStep === 'payments' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <AddSection title="Invoicing / Shifts">
                <AddField label="INVOICED (FREQUENCY)">
                  <select className="input w-full text-sm" value={newDriver.frequency} onChange={e => setNewDriver(d => ({ ...d, frequency: e.target.value }))}>
                    <option value="">—</option>
                    <option value="WEEKLY">Weekly</option>
                    <option value="MONTHLY">Every Month</option>
                  </select>
                </AddField>
                <AddField label="PAYMENT TERMS"><input className="input w-full text-sm" type="number" value={newDriver.payment_terms} onChange={e => setNewDriver(d => ({ ...d, payment_terms: e.target.value }))} /></AddField>
                <AddField label="OUTPUT PREF">
                  <select className="input w-full text-sm" value={newDriver.output_preference} onChange={e => setNewDriver(d => ({ ...d, output_preference: e.target.value }))}>
                    <option value="">ALL</option>
                    <option value="EMAIL">Email</option>
                    <option value="POST">Post</option>
                  </select>
                </AddField>
                <AddField label="INVOICE FOOTER">
                  <select className="input w-full text-sm" value={newDriver.invoice_footer} onChange={e => setNewDriver(d => ({ ...d, invoice_footer: e.target.value }))}>
                    <option value="">NONE</option>
                    <option value="STANDARD">Standard</option>
                    <option value="VAT">VAT Footer</option>
                  </select>
                </AddField>
                <AddField label="SHIFT REPORTING">
                  <label className="inline-flex items-center gap-2 text-sm text-gray-300">
                    <input type="checkbox" checked={newDriver.shift_reporting} onChange={e => setNewDriver(d => ({ ...d, shift_reporting: e.target.checked }))} />
                    <span>{newDriver.shift_reporting ? 'YES' : 'NO'}</span>
                  </label>
                </AddField>
              </AddSection>

              <AddSection title="Payments / VAT">
                <AddField label="PAYMENT ON">
                  <select className="input w-full text-sm" value={newDriver.payment_on_day} onChange={e => setNewDriver(d => ({ ...d, payment_on_day: e.target.value }))}>
                    {['monday','tuesday','wednesday','thursday','friday','saturday','sunday'].map(dd => (
                      <option key={dd} value={dd}>{dd.charAt(0).toUpperCase() + dd.slice(1)}</option>
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
                <AddField label="DISTRIBUTION">
                  <select className="input w-full text-sm" value={newDriver.distribution} onChange={e => setNewDriver(d => ({ ...d, distribution: e.target.value }))}>
                    <option value="POST">Post</option>
                    <option value="EMAIL">Email</option>
                  </select>
                </AddField>
                <AddField label="APPLY VAT?">
                  <label className="inline-flex items-center gap-2 text-sm text-gray-300">
                    <input type="checkbox" checked={newDriver.apply_vat} onChange={e => setNewDriver(d => ({ ...d, apply_vat: e.target.checked }))} />
                    <span>{newDriver.apply_vat ? 'YES' : 'NO'}</span>
                  </label>
                </AddField>
                <AddField label="VAT RATE (%)"><input className="input w-full text-sm" type="number" step="0.01" value={newDriver.vat_rate} onChange={e => setNewDriver(d => ({ ...d, vat_rate: e.target.value }))} /></AddField>
                <AddField label="EXCLUDE BOOKING FEE">
                  <label className="inline-flex items-center gap-2 text-sm text-gray-300">
                    <input type="checkbox" checked={newDriver.exclude_booking_fee} onChange={e => setNewDriver(d => ({ ...d, exclude_booking_fee: e.target.checked }))} />
                    <span>{newDriver.exclude_booking_fee ? 'YES' : 'NO'}</span>
                  </label>
                </AddField>
                <AddField label="COMMISSION (%)"><input className="input w-full text-sm" type="number" min="0" max="100" value={newDriver.commission_pct} onChange={e => setNewDriver(d => ({ ...d, commission_pct: e.target.value }))} /></AddField>
                <AddField label="AUTO POST">
                  <select className="input w-full text-sm" value={newDriver.auto_post} onChange={e => setNewDriver(d => ({ ...d, auto_post: e.target.value }))}>
                    <option value="SYSTEM_DEFAULT">System Default</option>
                    <option value="NEVER">Never</option>
                    <option value="ALWAYS">Always</option>
                  </select>
                </AddField>
              </AddSection>

              <AddSection title="Bank">
                <AddField label="BANK PAYMENT REF"><input className="input w-full text-sm" value={newDriver.bank_payment_ref} onChange={e => setNewDriver(d => ({ ...d, bank_payment_ref: e.target.value }))} /></AddField>
                <AddField label="USE SEPA">
                  <label className="inline-flex items-center gap-2 text-sm text-gray-300">
                    <input type="checkbox" checked={newDriver.use_sepa} onChange={e => setNewDriver(d => ({ ...d, use_sepa: e.target.checked }))} />
                    <span>{newDriver.use_sepa ? 'YES' : 'NO'}</span>
                  </label>
                </AddField>
                <AddField label="BANK NAME"><input className="input w-full text-sm" value={newDriver.bank_name} onChange={e => setNewDriver(d => ({ ...d, bank_name: e.target.value }))} /></AddField>
                <AddField label="ACCOUNT NAME"><input className="input w-full text-sm" value={newDriver.bank_account_name} onChange={e => setNewDriver(d => ({ ...d, bank_account_name: e.target.value }))} /></AddField>
                <AddField label="SORT CODE"><input className="input w-full text-sm" value={newDriver.sort_code} onChange={e => setNewDriver(d => ({ ...d, sort_code: e.target.value }))} /></AddField>
                <AddField label="ACCOUNT NUMBER"><input className="input w-full text-sm" value={newDriver.bank_account_number} onChange={e => setNewDriver(d => ({ ...d, bank_account_number: e.target.value }))} /></AddField>
              </AddSection>

              <AddSection title="Driver Fatigue">
                <AddField label="MAX WORK HOURS"><input className="input w-full text-sm" type="number" min="0" value={newDriver.fatigue_max_work_hours} onChange={e => setNewDriver(d => ({ ...d, fatigue_max_work_hours: e.target.value }))} /></AddField>
                <AddField label="MIN REST HOURS"><input className="input w-full text-sm" type="number" min="0" value={newDriver.fatigue_min_rest_hours} onChange={e => setNewDriver(d => ({ ...d, fatigue_min_rest_hours: e.target.value }))} /></AddField>
                <AddField label="EXCEED JOB BY (%)"><input className="input w-full text-sm" type="number" min="0" value={newDriver.fatigue_exceed_job_pct} onChange={e => setNewDriver(d => ({ ...d, fatigue_exceed_job_pct: e.target.value }))} /></AddField>
                <AddField label="SEND ALERT AT (%)"><input className="input w-full text-sm" type="number" min="0" max="100" value={newDriver.fatigue_send_alert_pct} onChange={e => setNewDriver(d => ({ ...d, fatigue_send_alert_pct: e.target.value }))} /></AddField>
              </AddSection>
            </div>
          )}

          {/* DOCUMENTS */}
          {wizardStep === 'documents' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {FILE_TYPES.map(t => (
                <div key={t.key} className="overflow-hidden rounded-lg border border-gray-700">
                  <div className="bg-gray-800 px-4 py-2.5 border-b border-gray-700 flex items-center justify-between">
                    <h3 className="text-xs font-semibold text-gray-400 tracking-widest uppercase">{t.label}</h3>
                    {docQueue[t.key] && (
                      <button
                        type="button"
                        onClick={() => setDocQueue(q => ({ ...q, [t.key]: null }))}
                        className="text-gray-500 hover:text-red-400"
                        title="Remove"
                      ><Trash2 size={14} /></button>
                    )}
                  </div>
                  <div className="bg-gray-900/60 p-4">
                    {docQueue[t.key] ? (
                      <div className="flex items-center gap-2 text-xs text-emerald-300">
                        <FileText size={14} />
                        <span className="truncate">{docQueue[t.key]?.name}</span>
                        <span className="text-gray-500 ml-auto">
                          {((docQueue[t.key]?.size || 0) / 1024).toFixed(1)} KB
                        </span>
                      </div>
                    ) : (
                      <label className="flex items-center justify-center gap-2 px-3 py-3 text-xs text-gray-400 border border-dashed border-gray-700 rounded cursor-pointer hover:border-amber-500 hover:text-amber-400 transition-colors">
                        <Upload size={14} />
                        Choose file
                        <input type="file" className="hidden" onChange={e => {
                          const f = e.target.files?.[0] || null
                          setDocQueue(q => ({ ...q, [t.key]: f }))
                        }} />
                      </label>
                    )}
                  </div>
                </div>
              ))}
              <p className="lg:col-span-2 text-xs text-gray-500">
                Files are uploaded after the driver record is created.
              </p>
            </div>
          )}

          {/* SITES */}
          {wizardStep === 'sites' && (
            <div className="overflow-hidden rounded-lg border border-gray-700">
              <div className="bg-gray-800 px-4 py-2.5 border-b border-gray-700">
                <h3 className="text-xs font-semibold text-gray-400 tracking-widest uppercase">Site Assignments</h3>
              </div>
              <table className="w-full text-sm">
                <thead className="bg-gray-800/40">
                  <tr>
                    {['Site Ref', 'Site Title', 'Assigned', 'Primary'].map(c => (
                      <th key={c} className="text-left px-4 py-2 text-xs font-semibold text-gray-400 tracking-widest uppercase">{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800/60 bg-gray-900/60">
                  {SITES.map(s => (
                    <tr key={s.code}>
                      <td className="px-4 py-3 text-amber-300 font-mono text-xs">{s.code}</td>
                      <td className="px-4 py-3 text-gray-200">{s.name}</td>
                      <td className="px-4 py-3">
                        <label className="inline-flex items-center gap-2 text-xs">
                          <input type="checkbox" checked={!!siteSel[s.code]?.assigned} onChange={e => {
                            setSiteSel(prev => ({
                              ...prev,
                              [s.code]: {
                                assigned: e.target.checked,
                                primary: e.target.checked ? prev[s.code].primary : false,
                              }
                            }))
                          }} />
                          <span className={clsx(siteSel[s.code]?.assigned ? 'text-emerald-400' : 'text-gray-500')}>
                            {siteSel[s.code]?.assigned ? 'Assigned' : 'Not assigned'}
                          </span>
                        </label>
                      </td>
                      <td className="px-4 py-3">
                        <input
                          type="radio"
                          name="primary_site"
                          checked={!!siteSel[s.code]?.primary}
                          disabled={!siteSel[s.code]?.assigned}
                          onChange={() => {
                            setSiteSel(prev => {
                              const next: typeof prev = {}
                              for (const code of Object.keys(prev)) {
                                next[code] = { assigned: prev[code].assigned, primary: code === s.code }
                              }
                              return next
                            })
                          }}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="bg-gray-900/60 p-4 border-t border-gray-700">
                <AddField label="NOTES">
                  <textarea className="input w-full text-sm" rows={3} value={newDriver.notes} onChange={e => setNewDriver(d => ({ ...d, notes: e.target.value }))} />
                </AddField>
              </div>
            </div>
          )}

          {/* Nav */}
          <div className="flex items-center justify-between pt-2">
            <button
              onClick={() => {
                const i = WIZARD_STEPS.findIndex(s => s.key === wizardStep)
                if (i > 0) setWizardStep(WIZARD_STEPS[i - 1].key)
              }}
              disabled={wizardStep === 'personal'}
              className="flex items-center gap-1 px-4 py-2 text-xs tracking-widest bg-gray-700 hover:bg-gray-600 text-gray-200 rounded disabled:opacity-30 transition-colors"
            >
              <ChevronLeft size={14} /> BACK
            </button>

            <div className="flex gap-3">
              <button
                onClick={() => { setActiveTab('SEARCH DRIVERS'); setAddError(''); setAddSuccess(false) }}
                className="px-5 py-2 text-xs bg-gray-800 hover:bg-gray-700 text-gray-400 rounded transition-colors tracking-widest"
              >
                CANCEL
              </button>
              {wizardStep === 'sites' ? (
                <button onClick={handleAddDriver} disabled={addLoading} className="btn-primary px-8 tracking-widest text-xs">
                  {addLoading ? 'ADDING...' : 'ADD DRIVER'}
                </button>
              ) : (
                <button
                  onClick={() => {
                    const i = WIZARD_STEPS.findIndex(s => s.key === wizardStep)
                    if (i < WIZARD_STEPS.length - 1) setWizardStep(WIZARD_STEPS[i + 1].key)
                  }}
                  className="flex items-center gap-1 px-4 py-2 text-xs tracking-widest bg-amber-600 hover:bg-amber-500 text-white rounded transition-colors"
                >
                  NEXT <ChevronRight size={14} />
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}