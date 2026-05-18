# Captain Taxi — Project State
**Last updated:** 2026-05-17 (session 7)
**Platform:** Multi-agent AI system to run a taxi company (Saskatoon & Regina, SK) with minimum human input.

---

## Architecture Overview

| Service | Port | Stack | Purpose |
|---|---|---|---|
| orchestrator | 8000 | FastAPI + Claude | Event router, escalations, daily digest |
| dispatch | 8001 | FastAPI | Trip booking, driver assignment, iCabbi/Autocab |
| customer | 8002 | FastAPI + Claude + Vapi + Twilio | Phone, SMS, WhatsApp, web chat |
| drivers | 8003 | FastAPI + Claude | Onboarding, scheduling, performance, HR |
| accounts | 8004 | FastAPI | Invoicing, driver payouts, QuickBooks |
| compliance | 8005 | FastAPI | Document renewals, auto-suspension sweeps |
| admin | 8006 | FastAPI + Claude | HR docs, owner digest, WhatsApp query handler |
| dashboard | 3000 | React + Vite + Tailwind | Owner-facing UI |

**Infrastructure:** PostgreSQL 16, Redis 7, Nginx reverse proxy, Docker Compose deployment.

---

## Escalation Rules (Owner contacted ONLY for)
1. Driver termination / firing
2. Expenses or payments > $500 (non-routine)
3. Legal threats, lawsuits, police, criminal matters
4. New contracts or partnership agreements
5. Anything that could seriously harm the company

Owner: WhatsApp +13068811542 | Amara (wife/co-decision-maker): +13068500760

---

## Status by Service

### ✅ ORCHESTRATOR (core/orchestrator/)
- Claude-powered event router: `orchestrator/agent.py` — DONE
- Escalation via Twilio WhatsApp: `orchestrator/escalation.py` — DONE
- Daily 8am digest to owner: `orchestrator/digest.py` — DONE
- FastAPI endpoints (events, escalations, logs, digest): `orchestrator/main.py` — DONE
- Redis pub/sub event listener — DONE
- DB models (AgentLog, Escalation, Driver, Trip, Customer, Vehicle, Document): `core/models.py` — DONE

### ✅ CUSTOMER AGENT (customer/)
- Claude conversation loop (multi-turn, tool use): `customer/ai/conversation.py` — DONE
- Tools: create_booking, get_trip_status, cancel_trip, fare_estimate, log_complaint, lookup_bookings — DONE
- Twilio webhook (SMS + WhatsApp inbound): `customer/routers/twilio.py` — DONE
- Vapi webhook (phone calls): `customer/routers/vapi.py` — DONE
- Web chat endpoint: `customer/routers/chat.py` — DONE
- DB models (customers, bookings, complaints): `customer/db/models.py` — DONE
- Dispatch service client: `customer/services/dispatch.py` — DONE
- Booking confirmation SMS / discount SMS: `customer/services/notify.py` — DONE

### ✅ DRIVERS AGENT (drivers/)
- Driver agent with Claude tool use: `drivers/agents/driver_agent.py` — DONE
- Onboarding agent: `drivers/agents/onboarding_agent.py` — DONE
- Communication agent (SMS/broadcast): `drivers/agents/communication_agent.py` — DONE
- Performance agent: `drivers/agents/performance_agent.py` — DONE
- Scheduling agent: `drivers/agents/scheduling_agent.py` — DONE
- Routers: drivers, onboarding, performance, scheduling, communication, webhooks — DONE
- Models: driver, suspension, termination, performance, schedule, communication — DONE
- Weekly jobs scheduler: `drivers/tasks/weekly_jobs.py` — DONE

### ✅ COMPLIANCE AGENT (compliance/)
- Daily sweep (auto-status update, threshold alerts): `compliance/services/sweep.py` — DONE
- Auto-suspend drivers with expired mandatory docs — DONE
- Document upload / management: `compliance/routers/documents.py` — DONE
- Compliance alerts service: `compliance/services/alerts.py` — DONE
- Suspension service: `compliance/services/suspension.py` — DONE
- Reports: `compliance/routers/reports.py` — DONE
- Required docs: drivers_abstract, criminal_record_check, taxi_license, sgi_insurance, vehicle_registration, safety_inspection

### ✅ ACCOUNTS AGENT (accounts/)
- Monthly corporate invoicing: `accounts/services/invoicing.py` — DONE
- Driver pay calculations: `accounts/services/driver_pay.py` — DONE
- QuickBooks integration: `accounts/services/quickbooks.py` — DONE (needs QB credentials)
- Revenue reporting: `accounts/services/revenue.py` — DONE
- Tax service: `accounts/services/tax.py` — DONE
- PDF generation: `accounts/utils/pdf.py` — DONE
- Expense tracking: `accounts/services/expenses.py` — DONE
- Payment reminders / escalation at 30 days — DONE

### ✅ ADMIN AGENT (admin/)
- Claude-powered HR doc drafting (offer letter, warning, policy, termination): `admin/agents/admin_agent.py` — DONE
- WhatsApp handler (owner queries): `admin/agents/whatsapp_handler.py` — DONE
- Daily digest generator: `admin/agents/digest.py` — DONE
- API routes: dashboard, drivers, compliance, hr, escalations, reports, announcements, settings — DONE
- Scheduler: `admin/scheduler.py` — DONE
- SendGrid email service: `admin/services/sendgrid_service.py` — DONE
- Twilio SMS service: `admin/services/twilio_service.py` — DONE

### ✅ DISPATCH AGENT (dispatch/)
- Claude + rule-based driver assignment engine: `dispatch/services/assignment_engine.py` — DONE
- Trip assignment with 90s timeout + Redis geo queries — DONE
- WebSocket manager (real-time driver updates): `dispatch/services/websocket_manager.py` — DONE
- Timeout worker: `dispatch/services/timeout_worker.py` — DONE
- Driver notifications: `dispatch/services/notifications.py` — DONE
- Routes: dispatch, driver, dashboard — DONE
- **NEW (session 5):** `TripStatus.noshow` + `noshow_at` timestamp — DONE
- **NEW (session 5):** Trip fields: `priority` (0/1/2), `via_address`, `customer_email`, `instructions`, `site` — DONE
- **NEW (session 5):** `DriverStatus`: `parked`, `dropping`, `bidding` added — DONE
- **NEW (session 5):** `POST /dispatch/trip/{id}/noshow` endpoint — DONE
- **NEW (session 5):** `DriverCreate` accepts `status`, `is_active`, `rating` for seeding — DONE
- **NEW (session 5):** Queue endpoint returns all 7 tabs: dispatch/pre_booked/booked/in_progress/completed/cancelled/noshow — DONE

### ✅ DASHBOARD (dashboard/)
- React + Vite + Tailwind app — FULLY BUILT (not a shell)
- Pages: Overview, Dispatch, Drivers, DriverProfile, Accounts, Compliance, Reports, Settings — all wired to real API
- Components: Layout, Sidebar, Header, StatCard, EscalationCard — polished dark UI
- Auto-refreshing hooks (15-30s intervals), TypeScript types, escalation approve/deny flow
- **FIXED (session 2):** nginx routing bug — all dashboard API paths now correctly route to admin:8006
- **NEW (session 5):** Dispatch.tsx fully rebuilt as iCabbi-style console:
  - Booking form: phone, name, email, pickup, dest, via, instructions, site, priority, scheduled time
  - Driver status pane: Parked / Dropping / Bidding / On Trip / Break sections with live counts
  - Live map: coordinate-based driver markers with hover tooltips + status legend
  - Job board: 7-tab table (DISPATCH/PRE-BOOKED/BOOKED/IN PROGRESS/COMPLETED/CANCELLED/NO SHOW)
  - Real-time WebSocket connection to dispatch dashboard WS
  - Cancel + no-show actions from job board
- **NEW (session 5):** `api.ts` dispatch methods: createTrip, listTrips, cancelTrip, noShowTrip, reassignTrip, listDispatchDrivers, getDispatchQueue, getDispatchMap, getDispatchStats
- **NEW (session 5):** `types/index.ts` dispatch types: DispatchTrip, DispatchDriver, DispatchQueue, QueueTrip, MapDriver, DispatchStats, TripCreatePayload

---

## Infrastructure & Deployment

- ✅ `docker-compose.yml` — all services defined, health checks, volumes
- ✅ `.env.example` — all required env vars documented
- ✅ `nginx.conf` — reverse proxy config exists
- ✅ `Dockerfile.orchestrator` — exists
- ✅ Per-service Dockerfiles — exist in each service folder
- ✅ `alembic/` — migrations present (root + dispatch have their own)
- ✅ `deploy.sh` — deployment script exists
- ⚠️ QuickBooks OAuth — credentials needed (`QB_CLIENT_ID`, `QB_CLIENT_SECRET`, `QB_REFRESH_TOKEN`, `QB_REALM_ID`)
- ⚠️ Vapi — needs Vapi API key and phone number configured
- ⚠️ iCabbi/Autocab — dispatch integration needs live credentials

---

## Known Gaps / Next Tasks
- [x] Dashboard: nginx routing bug fixed — all dashboard API paths now route to admin:8006
- [x] E2E test script: `scripts/test_e2e.py` — full trip flow (chat → dispatch → assign → lifecycle → complete)
- [x] Bug fix: `customer/services/dispatch.py` — wrong URL paths (`/trips` → `/dispatch/trip`), missing `city` field, `pickup_time` renamed to `scheduled_for`
- [x] Bug fix: `customer/ai/tools.py` — added `city` field to `create_booking` tool
- [x] Bug fix: `customer/ai/conversation.py` — passes `city` and `scheduled_for` to dispatch client
- [ ] Run E2E test against live Docker stack: `python scripts/test_e2e.py`
- [ ] Apply Alembic migration `002_icabbi_driver_fields` on staging/prod DB before next iCabbi import
- [ ] Settings: add mandatory-field config UI so the manual "Add Driver" form's required-field rules become user-tunable (currently hard-coded in `Drivers.tsx` `handleAddDriver`)
- [ ] QuickBooks: complete OAuth flow and token refresh logic
- [ ] Vapi: configure phone number and test call flow end-to-end
- [ ] iCabbi/Autocab: integrate live dispatch API (currently simulated)
- [ ] Load test / stress test with simulated driver fleet
- [ ] Production deployment on a server (VPS or cloud)

---

## Key Contacts (hardcoded in codebase)
- Owner: +13068811542
- Amara (wife/co-decision-maker): +13068500760
- Saskatoon taxi line: 306-242-0000
- Regina taxi line: 306-775-2222
- Commission split: 70% driver / 30% company

---

## Session Log

| Session | Date | Summary |
|---|---|---|
| 1 | 2026-04-?? | Initial build — all 8 services scaffolded and implemented |
| 2 | 2026-04-10 | Dashboard fully wired to real API; nginx routing bug fixed (all dashboard paths now → admin:8006) |
| 3 | 2026-04-12 | Created `CLAUDE.md` — auto-read instructions for Claude at project open; established session logging convention in `PROJECT_STATE.md` |
| 4 | 2026-04-12 | Fixed 3 bugs in customer→dispatch API client (wrong URLs, missing city, wrong field name); added city to booking tool; wrote `scripts/test_e2e.py` full E2E test |
| 5 | 2026-04-12 | iCabbi feature parity: added noshow status/endpoint, priority/via/email/instructions/site fields, parked/dropping/bidding driver statuses, 7-tab queue endpoint, full Dispatch.tsx console rebuild (booking form + driver pane + live map + job board), extended E2E test |
| 6 | 2026-04-12 | GitHub repo: https://github.com/Tengorra/captain-taxi | Vercel dashboard deployed: https://captain-taxi-dashboard.vercel.app | Git → GitHub connected; backend needs Railway deploy + VITE_API_URL set on Vercel |
| 7 | 2026-05-17 | Drivers module re-aligned to iCabbi export schema. Added ~30 new first-class columns to `drivers` table (first_name/last_name/aka/mobile/gender/address, badge_type/school_badge_expiry/ni_number, icabbi_ref/vehicle_ref/start_date, full device/app metadata, last_active_at/last_updated_at, frequency/payment_period/payment_terms/output_preference/si_id) + `icabbi_config` JSON catch-all for the ~30 deep app-config flags. Relaxed NOT NULL on name/phone and dropped UNIQUE on phone so blank/duplicate iCabbi rows import cleanly. Migration: `alembic/versions/002_icabbi_driver_fields.py`. Admin `POST /drivers/` accepts the full iCabbi field set, dedupes by `icabbi_ref` (returns 409 → dashboard counts as dupe), handles DD/MM/YYYY dates, treats 1969 as null, recovers scientific-notation phones, dumps unknown columns into icabbi_config. Dashboard Drivers table redesigned to iCabbi-style columns (REF/FIRST/LAST/MOBILE/BADGE/EXPIRIES/VEHICLE/LAST ACTIVE/ACTIVE). Manual-entry mandatory-field rules stay client-side for now (deferred to a future Settings change). |
