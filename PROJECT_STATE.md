# Captain Taxi — Project State
**Last updated:** 2026-05-19 (session 9)
**Platform:** Multi-agent AI system to run a taxi company (Saskatoon & Regina, SK) with minimum human input.

---

## Architecture Overview

| Service | Port | Stack | Purpose |
|---|---|---|---|
| orchestrator | 8000 | FastAPI + Claude | Event router, escalations, daily digest |
| dispatch | 8001 | FastAPI | Trip booking, driver assignment, iCabbi/Autocab |
| customer | 8002 | FastAPI + Claude + ElevenLabs + Twilio | Phone, SMS, WhatsApp, web chat |
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
- ElevenLabs Conversational AI webhook (phone calls): `customer/routers/elevenlabs.py` — DONE (replaces Vapi as of session 8)
- ElevenLabs agent config (paste-into-dashboard): `customer/elevenlabs/agent_config.json` — DONE
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
- ⚠️ ElevenLabs Conversational AI — needs `ELEVENLABS_API_KEY`, `ELEVENLABS_AGENT_ID`, `ELEVENLABS_WEBHOOK_SECRET` in `.env`; agent created in dashboard from `customer/elevenlabs/agent_config.json` and connected to the Twilio Saskatoon + Regina voice numbers
- ⚠️ iCabbi/Autocab — dispatch integration needs live credentials

---

## ⚠️ Blocking E2E Failures (session 9, 2026-05-19)

E2E verification ran against a native Postgres 16 + Redis 7 (Docker daemon
unavailable in the Code-on-Web container, so `docker compose up` could not
be executed directly). Each failure below was reproduced by importing the
service and POSTing real requests; all of them would also surface inside
Docker.

**Blocker 1 — `.env.example` `POSTGRES_HOST=postgres` doesn't match compose service `db`.**
`docker-compose.yml` defines the Postgres service as `db:` (line ~). All
services receive `POSTGRES_HOST=postgres` via `env_file: .env`. The
hostname `postgres` is not resolvable inside the compose network, so every
service that uses the value will fail to connect on first DB call.
`orchestrator` (`core/config.py:13`) also defaults `postgres_host="postgres"`
— same bug. Fix: change `.env.example` to `POSTGRES_HOST=db` and the
`core/config.py` default to `"db"`.

**Blocker 2 — Root and dispatch alembic chains collide on the shared `alembic_version` table.**
`alembic/env.py` and `dispatch/alembic/env.py` both use the default
`alembic_version` table on the same Postgres DB. Both define their own
revision `001`. After orchestrator's CMD stamps `002`, dispatch's
container CMD (`alembic upgrade head && uvicorn …`) fails with
`Can't locate revision identified by '002'` and uvicorn never starts.
Reproduced: `cd dispatch && alembic upgrade head` after root migration
gives `FAILED: Can't locate revision identified by '002'`. Fix options:
(a) give each alembic chain its own `version_table` name in `env.py`
(`context.configure(..., version_table="alembic_version_dispatch")`),
(b) merge dispatch's migration into the root chain, or (c) drop the
`&& uvicorn` chaining in `dispatch/Dockerfile`. (a) is the smallest change.

**Blocker 3 — Schema fragmentation: per-service models don't match root migration's `drivers` table.**
Root migration `001` creates `drivers` with columns from `core/models.py`
(license_number, taxi_license_number, etc.). Dispatch's `Driver` model
(`dispatch/models/driver.py`) expects `vehicle_plate`, `vehicle_model`,
`is_active`, `last_lat`, `last_lng`, `last_location_at`. Each service uses
`Base.metadata.create_all()` at startup, which **skips existing tables**
(no ALTER). Result: `POST /driver` on dispatch produces
`UndefinedColumnError: column "vehicle_plate" of relation "drivers" does
not exist` — and E2E step 2/10 (`seed_driver`) fails with HTTP 500.
Same class of bug exists for any model column added in a service after
the root migration ran.

**Blocker 4 — `customers.id` type mismatch breaks `bookings`/`complaints`/`conversation_logs` FKs.**
Root migration creates `customers.id` as `VARCHAR(36)`. Customer service
(`customer/db/models.py:51`) defines `Customer.id` as `UUID(as_uuid=True)`
and `Booking.customer_id`, `Complaint.customer_id`, `ConversationLog.customer_id`
as `UUID`. On customer service startup, `create_all` raises
`asyncpg.exceptions.DatatypeMismatchError: foreign key constraint
"bookings_customer_id_fkey" cannot be implemented. Key columns
"customer_id" and "id" are of incompatible types: uuid and character
varying.` → bookings/complaints/conversation_logs tables are never
created. Any booking write from the chat/voice flow will 500. Fix:
align types — either change root migration `001` to use `UUID` for `id`
columns, or change service models to `String(36)`. Affects: `customers`,
`drivers`, `trips`, `vehicles` (all `String(36)` in root, `UUID` in service models).

**Blocker 5 — `docker compose up` cannot be executed in Code-on-Web.**
The Code-on-Web container does not expose `/var/run/docker.sock`, so
neither `docker compose up` nor `docker compose run --rm orchestrator alembic upgrade head`
can be run from this session. Running `docker compose config` (no daemon
required) succeeds. Verification beyond that requires either (a) a
self-hosted runner / VPS, (b) running the stack on the owner's machine,
or (c) Railway/Render deployment. **The orchestrator service was never
exercised in this session** for the same reason — its only entrypoint
is its container CMD.

**Non-blocking findings:**
- `docker-compose.yml` uses the obsolete top-level `version:` key
  (compose warns). Harmless, remove when convenient.
- Two unrelated unused fields in the dispatch test path: `DRIVER_LAT`,
  `DRIVER_LNG` constants in `scripts/test_e2e.py` are correct; the test
  itself reads cleanly until it hits Blocker 3.

**What was verified successfully:**
- `docker compose config` parses the YAML for all 11 services (no
  structural errors).
- Migration chain `001 → 002` (root) parses and applies cleanly on a
  real Postgres 16 — see `alembic upgrade head` output.
- Migration `002_icabbi_driver_fields.py` correctly adds all 30 iCabbi
  columns, drops UNIQUE on `phone`, relaxes NOT NULL on `name`/`phone`/`city`,
  and creates `ix_drivers_icabbi_ref` (verified with `\d drivers`).
- `customer/main.py`, `dispatch/main.py`, `drivers/main.py` import
  cleanly under their respective Python 3.11 venvs (per-service deps
  installed from each `requirements.txt`).
- `dispatch` service starts under uvicorn and `/health` returns 200.
- `customer` service starts under uvicorn and `/health` returns
  `{status: ok, redis: ok}` — but logs the FK error from Blocker 4 at
  init.
- E2E step 1/10 (health checks) passes against the two services.
- E2E step 2/10 (driver seed) is where the test halts — root cause is
  Blocker 3, not a script bug.

## Known Gaps / Next Tasks
- [x] Dashboard: nginx routing bug fixed — all dashboard API paths now route to admin:8006
- [x] E2E test script: `scripts/test_e2e.py` — full trip flow (chat → dispatch → assign → lifecycle → complete)
- [x] Bug fix: `customer/services/dispatch.py` — wrong URL paths (`/trips` → `/dispatch/trip`), missing `city` field, `pickup_time` renamed to `scheduled_for`
- [x] Bug fix: `customer/ai/tools.py` — added `city` field to `create_booking` tool
- [x] Bug fix: `customer/ai/conversation.py` — passes `city` and `scheduled_for` to dispatch client
- [ ] Run E2E test against live Docker stack: `python scripts/test_e2e.py` — **ATTEMPTED session 9, blocked by 4 schema/config bugs documented above ("Blocking E2E Failures"). Test halts at step 2/10 (driver seed) with HTTP 500 due to schema drift on `drivers` table.**
- [ ] Apply Alembic migration `002_icabbi_driver_fields` on staging/prod DB before next iCabbi import
- [x] Settings: mandatory-field config UI — manual "Add Driver" required fields are now user-tunable from Settings page (stored in `driver_required_fields` setting; default preserves prior behavior: first_name, last_name, phone)
- [ ] QuickBooks: complete OAuth flow and token refresh logic
- [ ] ElevenLabs Conversational AI: create agent in dashboard from `customer/elevenlabs/agent_config.json` (replace `BASE_URL`), connect Twilio numbers, set webhook secret, and test inbound call → create_booking → trip appears in dispatch portal → dispatcher manually enters into iCabbi
- [x] **Decision (session 8):** Voice stack is ElevenLabs Conversational AI + Twilio. Vapi has been removed. Dispatch flow: caller → ElevenLabs agent → tool webhook → our dispatch service. Dispatchers manually re-enter trips into iCabbi for now; future work is iCabbi API integration or migrating off iCabbi entirely.
- [ ] iCabbi/Autocab: integrate live dispatch API (currently simulated). Booking-creation endpoint to use: `POST /bookings/addComplex` — see https://api.icabbicanada.com/docs/index.html#!/bookings/bookingsAddComplex (Canada region). Open from a browser; the spec is host-allowlisted and not reachable from the Code-on-Web container's network. When implementing, add a feature flag in dispatch service so it stays off until iCabbi creds are in `.env`.
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
| 9 | 2026-05-19 | E2E verification (read-only, no feature work). Docker daemon unavailable in Code-on-Web — used native Postgres 16 + Redis 7. Root alembic chain `001 → 002` applies cleanly; migration 002 verified to add all 30 iCabbi columns, drop UNIQUE on phone, and relax NOT NULL on name/phone/city. `customer`/`dispatch`/`drivers` import & start cleanly; `/health` returns 200 on both. `scripts/test_e2e.py` halts at step 2/10. Logged 4 blocking bugs + 1 environmental constraint in new "Blocking E2E Failures" section: (1) `.env.example` POSTGRES_HOST=postgres doesn't match compose service `db`, (2) root and dispatch alembic chains collide on shared `alembic_version` table (dispatch container's `alembic upgrade head && uvicorn` shortcircuits, dispatch never starts), (3) per-service models drift from root migration's `drivers` schema (dispatch driver insert → `column "vehicle_plate" does not exist`), (4) `customers.id` is `VARCHAR(36)` in migration but `UUID` in customer models → bookings/complaints/conversation_logs FKs can't be created. No code changes made — verification only. |
| 8 | 2026-05-19 | (1) Settings UI now controls manual "Add Driver" required-field rules. New setting `driver_required_fields` (CSV) seeded with default `first_name,last_name,phone`. `Drivers.tsx` validates dynamically against the setting and renders `*` markers from the same source. `PUT /settings/{key}` now upserts. (2) **Voice stack migrated from Vapi → ElevenLabs Conversational AI + Twilio.** Deleted `customer/routers/vapi.py` and `customer/vapi/`. Added `customer/routers/elevenlabs.py` (tool + post-call webhooks, HMAC signature verification, path-routed + body-routed tool shapes). Added `customer/elevenlabs/agent_config.json` for dashboard paste-in. Swapped `vapi_*` config for `elevenlabs_*` in `customer/config.py` and `customer/.env.example`. CLAUDE.md now contains an explicit "NOT Vapi" rule. |
| 7 | 2026-05-17 | Drivers module re-aligned to iCabbi export schema. Added ~30 new first-class columns to `drivers` table (first_name/last_name/aka/mobile/gender/address, badge_type/school_badge_expiry/ni_number, icabbi_ref/vehicle_ref/start_date, full device/app metadata, last_active_at/last_updated_at, frequency/payment_period/payment_terms/output_preference/si_id) + `icabbi_config` JSON catch-all for the ~30 deep app-config flags. Relaxed NOT NULL on name/phone and dropped UNIQUE on phone so blank/duplicate iCabbi rows import cleanly. Migration: `alembic/versions/002_icabbi_driver_fields.py`. Admin `POST /drivers/` accepts the full iCabbi field set, dedupes by `icabbi_ref` (returns 409 → dashboard counts as dupe), handles DD/MM/YYYY dates, treats 1969 as null, recovers scientific-notation phones, dumps unknown columns into icabbi_config. Dashboard Drivers table redesigned to iCabbi-style columns (REF/FIRST/LAST/MOBILE/BADGE/EXPIRIES/VEHICLE/LAST ACTIVE/ACTIVE). Manual-entry mandatory-field rules stay client-side for now (deferred to a future Settings change). |
