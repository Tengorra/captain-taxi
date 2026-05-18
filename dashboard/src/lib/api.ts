// In production (Vercel), set VITE_API_URL to your Railway backend URL
// e.g. https://captain-taxi-api.railway.app
// Locally it proxies via nginx at /api
// In production (Vercel), set VITE_API_URL env var to your Railway backend URL
// e.g. https://captain-taxi-api.railway.app
// Locally it proxies via nginx at /api
declare const __VITE_API_URL__: string | undefined
const BASE: string = (() => {
  try { return (import.meta as {env?: {VITE_API_URL?: string}}).env?.VITE_API_URL ?? '/api' }
  catch { return '/api' }
})()

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(err || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  // Dashboard
  overview: () => request<import('../types').OverviewStats>('/dashboard/overview'),
  alerts: (limit = 20) => request<import('../types').Alert[]>(`/dashboard/alerts?limit=${limit}`),
  revenueChart: (days = 7) => request<import('../types').ChartPoint[]>(`/dashboard/revenue/chart?days=${days}`),
  markAlertRead: (id: number) => request(`/dashboard/alerts/${id}/read`, { method: 'POST' }),
  resolveAlert: (id: number) => request(`/dashboard/alerts/${id}/resolve`, { method: 'POST' }),

  // Drivers
  listDrivers: (params?: { city?: string; status?: string; search?: string }) => {
    const q = new URLSearchParams(params as Record<string, string>).toString()
    return request<import('../types').Driver[]>(`/drivers/${q ? '?' + q : ''}`)
  },
  getDriver: (id: string) => request<import('../types').Driver>(`/drivers/${id}`),
  updateDriver: (id: string, data: Partial<import('../types').Driver>) =>
    request(`/drivers/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  suspendDriver: (id: string, reason: string) =>
    request(`/drivers/${id}/suspend`, { method: 'POST', body: JSON.stringify({ reason }) }),
  activateDriver: (id: string) => request(`/drivers/${id}/activate`, { method: 'POST' }),
  driverActivityLog: (id: string) =>
    request<import('../types').ActivityLog[]>(`/drivers/${id}/activity`),
  messageDriver: (id: string, message: string) =>
    request(`/drivers/${id}/message`, { method: 'POST', body: JSON.stringify({ message }) }),
  driverTrips: (id: string) => request<import('../types').Trip[]>(`/drivers/${id}/trips`),
  driverDocuments: (id: string) => request<import('../types').DriverDocument[]>(`/drivers/${id}/documents`),
  createDriver: (data: {
    // Identity — all optional; UI enforces its own mandatory-field rules.
    name?: string
    first_name?: string
    last_name?: string
    aka?: string
    gender?: string
    sex?: string
    address?: string
    email?: string
    phone?: string
    mobile?: string
    city?: string
    // Status
    status?: string
    is_active_flag?: boolean
    is_deleted?: boolean
    driver_type?: string
    // iCabbi linkage
    icabbi_driver_id?: string
    icabbi_ref?: string
    vehicle_ref?: string
    start_date?: string
    // Licensing
    licence_number?: string
    licence_expiry?: string
    badge_number?: string
    badge_expiry?: string
    badge_type?: string
    school_badge_expiry?: string
    ni_number?: string
    // Vehicle
    vehicle_make?: string
    vehicle_model?: string
    vehicle_year?: number
    vehicle_plate?: string
    vehicle_color?: string
    // Device / app
    imei_udid?: string
    app_version?: string
    legacy_version?: string
    installed_legacy_version?: string
    phone_os?: string
    phone_os_version?: string
    phone_manufacturer?: string
    phone_model?: string
    phone_locked?: boolean
    profile_photo?: string
    // Activity
    last_updated_at?: string
    last_active_at?: string
    // Payments
    commission_rate?: number
    payment_type?: string
    payment_period?: number
    payment_terms?: number
    last_payment_at?: string
    output_preference?: string
    frequency?: string
    frequency_day?: number
    si_id?: string
    // Catch-all
    icabbi_config?: Record<string, unknown>
    notes?: string
  }) =>
    request<import('../types').Driver>('/drivers/', { method: 'POST', body: JSON.stringify(data) }),

  // Escalations
  listEscalations: (status?: string) =>
    request<import('../types').Escalation[]>(`/escalations/${status ? '?status=' + status : ''}`),
  decideEscalation: (id: number, decision: 'approved' | 'denied', note?: string) =>
    request(`/escalations/${id}/decide`, { method: 'POST', body: JSON.stringify({ decision, note }) }),

  // Compliance
  complianceOverview: () => request<import('../types').ComplianceDriver[]>('/compliance/overview'),
  expiringDocs: (days = 30) => request<any[]>('/compliance/expiring?days=' + days),

  // Reports
  revenueReport: (start: string, end: string, city?: string) => {
    const params = new URLSearchParams({ start_date: start, end_date: end })
    if (city) params.set('city', city)
    return request<import('../types').RevenueData>('/reports/revenue?' + params)
  },
  weeklyDownloadUrl: (weekOffset = 0) =>
    `${BASE}/reports/weekly/download?week_offset=${weekOffset}`,

  // Announcements
  sendAnnouncement: (message: string, targetCity?: string) =>
    request('/announcements/send', {
      method: 'POST',
      body: JSON.stringify({ message, target_city: targetCity }),
    }),
  announcementHistory: () => request('/announcements/history'),

  // Settings
  getSettings: () => request<import('../types').AppSettings>('/settings/'),
  updateSetting: (key: string, value: string) =>
    request(`/settings/${key}`, { method: 'PUT', body: JSON.stringify({ value }) }),

  // HR
  draftHRDocument: (doc_type: string, driver_id?: string, context?: Record<string, unknown>) =>
    request('/hr/draft', {
      method: 'POST',
      body: JSON.stringify({ doc_type, driver_id, context: context || {} }),
    }),

  // ── Dispatch (direct to dispatch service) ──────────────────────────────
  createTrip: (data: import('../types').TripCreatePayload) =>
    request<import('../types').DispatchTrip>('/dispatch/trip', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getTrip: (id: string) =>
    request<import('../types').DispatchTrip>(`/dispatch/trip/${id}`),
  listTrips: (params?: { status?: string; city?: string; limit?: number }) => {
    const q = new URLSearchParams(params as Record<string, string>).toString()
    return request<import('../types').DispatchTrip[]>(`/dispatch/trips${q ? '?' + q : ''}`)
  },
  cancelTrip: (id: string, reason?: string) =>
    request<import('../types').DispatchTrip>(`/dispatch/trip/${id}/cancel`, {
      method: 'POST',
      body: JSON.stringify({ reason: reason || '' }),
    }),
  noShowTrip: (id: string) =>
    request<import('../types').DispatchTrip>(`/dispatch/trip/${id}/noshow`, { method: 'POST' }),
  reassignTrip: (id: string, driver_id: string, reason?: string) =>
    request<import('../types').DispatchTrip>(`/dispatch/trip/${id}/reassign`, {
      method: 'POST',
      body: JSON.stringify({ driver_id, reason: reason || '' }),
    }),

  // Dispatch drivers (dispatch service)
  listDispatchDrivers: (params?: { city?: string; status?: string }) => {
    const q = new URLSearchParams(params as Record<string, string>).toString()
    return request<import('../types').DispatchDriver[]>(`/dispatch/driver${q ? '?' + q : ''}`)
  },

  // Dispatch dashboard
  getDispatchQueue: (city?: string, history_hours = 4) => {
    const q = new URLSearchParams({ ...(city ? { city } : {}), history_hours: String(history_hours) }).toString()
    return request<import('../types').DispatchQueue>(`/dispatch/dashboard/queue?${q}`)
  },
  getDispatchMap: (city?: string) => {
    const q = city ? `?city=${city}` : ''
    return request<import('../types').DispatchMapData>(`/dispatch/dashboard/map${q}`)
  },
  getDispatchStats: (city?: string) => {
    const q = city ? `?city=${city}` : ''
    return request<import('../types').DispatchStats>(`/dispatch/dashboard/stats${q}`)
  },

  // ── BOT (live calls) ─────────────────────────────────────────────────────
  callHistory: (callId: string) =>
    request<{ call_id: string; events: import('../types').BotCallEvent[] }>(
      `/bot/calls/${callId}/history`,
    ),
  transferCall: (
    callId: string,
    body: { twilio_call_sid: string; city?: string; reason?: string },
  ) =>
    request(`/bot/calls/${callId}/transfer`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
}

// Live call-log WebSocket URL. The bot service exposes it at /calls/stream;
// nginx proxies it under /ws/calls/stream.
export function callsStreamUrl(callId?: string): string {
  const isHttps =
    typeof window !== 'undefined' && window.location.protocol === 'https:'
  const proto = isHttps ? 'wss' : 'ws'
  const host =
    typeof window !== 'undefined' ? window.location.host : 'localhost'
  const qs = callId ? `?call_id=${encodeURIComponent(callId)}` : ''
  return `${proto}://${host}/ws/calls/stream${qs}`
}
