/**
 * Captain Taxi — Mock API Server
 * Runs on port 8006, mirrors the real admin backend.
 * Data lives in memory — resets on restart.
 *
 * Usage:  node mock-server.js
 */
const http = require('http')
const PORT = 8006

// ── In-memory store ───────────────────────────────────────────────────────────
const drivers = []

// ── Helpers ───────────────────────────────────────────────────────────────────
function respond(res, status, data) {
  res.writeHead(status, { 'Content-Type': 'application/json' })
  res.end(JSON.stringify(data))
}

function parseBody(req) {
  return new Promise(resolve => {
    let body = ''
    req.on('data', chunk => (body += chunk))
    req.on('end', () => {
      try { resolve(body ? JSON.parse(body) : {}) }
      catch { resolve({}) }
    })
  })
}

// ── Server ────────────────────────────────────────────────────────────────────
const server = http.createServer(async (req, res) => {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*')
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,PATCH,PUT,DELETE,OPTIONS')
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type')
  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return }

  const url   = new URL(req.url, `http://localhost:${PORT}`)
  const path  = url.pathname
  const method = req.method
  const body  = await parseBody(req)

  console.log(`${method} ${path}`)

  // ── Dashboard ──
  if (path === '/api/dashboard/overview') {
    return respond(res, 200, {
      drivers_online:      { saskatoon: 3, regina: 2, total: 5 },
      active_trips:        { saskatoon: 2, regina: 1, total: 3 },
      today:               { trips: 24, revenue: 840.50, revenue_change_pct: 12.5 },
      alerts:              { unread: 2, critical: 0 },
      pending_escalations: 1,
      timestamp:           new Date().toISOString(),
    })
  }

  if (path === '/api/dashboard/alerts') return respond(res, 200, [])
  if (path === '/api/dashboard/revenue/chart') return respond(res, 200, [])

  // ── Drivers list ──
  if (path === '/api/drivers/' || path === '/api/drivers') {
    if (method === 'GET') {
      let result = [...drivers]
      const search = url.searchParams.get('search')
      const status = url.searchParams.get('status')
      if (search && search !== 'undefined')
        result = result.filter(d => d.name?.toLowerCase().includes(search.toLowerCase()) || d.phone?.includes(search))
      if (status && status !== 'undefined')
        result = result.filter(d => d.status === status)
      return respond(res, 200, result)
    }

    if (method === 'POST') {
      const name = (body.name || `${body.first_name || ''} ${body.last_name || ''}`).trim()
      if (!name || !body.phone) return respond(res, 400, { detail: 'Name and phone are required' })

      const driver = {
        id:               `drv-${Date.now()}`,
        name,
        first_name:       body.first_name        || '',
        last_name:        body.last_name         || '',
        phone:            body.phone,
        email:            body.email             || null,
        city:             body.city              || 'saskatoon',
        status:           body.status            || 'pending',
        driver_type:      body.driver_type       || 'regular',
        performance_score: 100,
        commission_rate:  body.commission_rate   || 0.30,
        vehicle_plate:    body.vehicle_plate     || null,
        vehicle_model:    body.vehicle_model     || null,
        badge_number:     body.badge_number      || null,
        badge_expiry:     body.badge_expiry      || null,
        badge_type:       body.badge_type        || null,
        licence_number:   body.licence_number    || null,
        licence_expiry:   body.licence_expiry    || null,
        tax_number:       body.tax_number        || null,
        address:          body.address           || null,
        mobile_phone:     body.mobile_phone      || null,
        other_phone:      body.other_phone       || null,
        sex:              body.sex               || null,
        aka:              body.aka               || null,
        payment_on:       body.payment_on        || 'sunday',
        payment_type:     body.payment_type      || 'cash',
        bank_name:        body.bank_name         || null,
        bank_account_number: body.bank_account_number || null,
        sort_code:        body.sort_code         || null,
        notes:            body.notes             || null,
        total_trips:      0,
        total_earnings:   0,
        documents:        [],
        created_at:       new Date().toISOString(),
      }
      drivers.push(driver)
      console.log(`  → Created driver: ${driver.name} (${driver.id})`)
      return respond(res, 200, driver)
    }
  }

  // ── Single driver ──
  const driverBase = path.match(/^\/api\/drivers\/([^/]+)$/)
  if (driverBase) {
    const id     = driverBase[1]
    const driver = drivers.find(d => d.id === id)

    if (method === 'GET') {
      if (!driver) return respond(res, 404, { detail: 'Driver not found' })
      return respond(res, 200, driver)
    }

    if (method === 'PATCH') {
      if (!driver) return respond(res, 404, { detail: 'Driver not found' })
      Object.assign(driver, body)
      console.log(`  → Updated driver: ${driver.name}`)
      return respond(res, 200, { ok: true, driver })
    }
  }

  // ── Driver actions ──
  const suspend  = path.match(/^\/api\/drivers\/([^/]+)\/suspend$/)
  const activate = path.match(/^\/api\/drivers\/([^/]+)\/activate$/)
  const message  = path.match(/^\/api\/drivers\/([^/]+)\/message$/)
  const trips    = path.match(/^\/api\/drivers\/([^/]+)\/trips$/)
  const docs     = path.match(/^\/api\/drivers\/([^/]+)\/documents$/)

  if (suspend  && method === 'POST') {
    const d = drivers.find(x => x.id === suspend[1])
    if (d) { d.status = 'suspended'; console.log(`  → Suspended: ${d.name}`) }
    return respond(res, 200, { ok: true })
  }
  if (activate && method === 'POST') {
    const d = drivers.find(x => x.id === activate[1])
    if (d) { d.status = 'active'; console.log(`  → Activated: ${d.name}`) }
    return respond(res, 200, { ok: true })
  }
  if (message  && method === 'POST') {
    console.log(`  → SMS to ${message[1]}: "${body.message}"`)
    return respond(res, 200, { ok: true })
  }
  if (trips    && method === 'GET') return respond(res, 200, [])
  if (docs     && method === 'GET') return respond(res, 200, [])

  // ── Other routes (return safe empty responses) ──
  if (path.startsWith('/api/escalations'))  return respond(res, 200, [])
  if (path.startsWith('/api/compliance'))   return respond(res, 200, [])
  if (path.startsWith('/api/announcements'))return respond(res, 200, [])
  if (path.startsWith('/api/settings'))     return respond(res, 200, {})
  if (path.startsWith('/api/hr'))           return respond(res, 200, { content: '[AI Draft] This is a mock HR document.' })
  if (path.startsWith('/api/reports'))      return respond(res, 200, {
    start_date: '', end_date: '', total_trips: 0, total_revenue: 0,
    company_revenue: 0, driver_pay: 0, by_city: {}, daily: {},
  })

  respond(res, 404, { detail: 'Not found' })
})

server.listen(PORT, () => {
  console.log(`\n╔══════════════════════════════════════╗`)
  console.log(`║  Captain Taxi Mock API               ║`)
  console.log(`║  http://localhost:${PORT}              ║`)
  console.log(`║  Data resets when you restart        ║`)
  console.log(`╚══════════════════════════════════════╝\n`)
})
