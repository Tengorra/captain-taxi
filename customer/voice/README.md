# ElevenLabs Agents — Captain Taxi setup

This service is the back-end for an ElevenLabs voice agent. Each tool in
the ElevenLabs dashboard is a separate REST endpoint here.

## 1. Env vars

Add to `customer/.env`:

```
ELEVENLABS_API_KEY=...               # workspace API key
ELEVENLABS_AGENT_ID=...              # agent created in the dashboard
ELEVENLABS_WEBHOOK_SECRET=<random>   # shared secret (32+ chars)
ELEVENLABS_AUTH_HEADER=X-Captain-Auth   # optional, default is fine
```

## 2. ElevenLabs dashboard — Agent settings

1. **Create an Agent** in the ElevenLabs Agents dashboard.
2. **Voice** — pick (or upload) the voice you want callers to hear.
3. **First message** — e.g. "Thank you for calling Captain Taxi! How can I help?"
4. **System prompt** — paste the one in `customer/vapi/assistant_config.json`
   under `model.systemPrompt` (it's already written for a phone agent —
   short responses, no bullet points, etc.).
5. **LLM** — Anthropic Claude (Sonnet 4.6 or later).
6. **Knowledge base** — optional; the FAQ block in `system_prompt.py`
   can be uploaded as a doc.

## 3. ElevenLabs dashboard — Tools

For each tool below, create a **Webhook** tool with:

- **Method:** POST
- **Content type:** application/json
- **Auth header:** `X-Captain-Auth = <ELEVENLABS_WEBHOOK_SECRET>`
  (mark the value as a Secret in the dashboard)
- **URL:** `https://customer.captain.taxi/voice/<endpoint>`

System parameters available in the dashboard:

- `{{system__caller_id}}`  →  pass as `caller_phone`
- `{{system__conversation_id}}`  →  pass as `conversation_id`

### create_booking
- URL: `https://customer.captain.taxi/voice/booking`
- Body parameters (LLM fills these from the conversation):
  - `pickup_address` (string, required)
  - `dropoff_address` (string, required)
  - `customer_name` (string)
  - `customer_phone` (string) — if customer reads a number aloud
  - `caller_phone` → `{{system__caller_id}}`
  - `num_passengers` (integer, default 1)
  - `pickup_time` (string: "ASAP" or ISO 8601)
  - `notes` (string)
  - `city` (string: "saskatoon" | "regina")
  - `conversation_id` → `{{system__conversation_id}}`

### get_trip_status
- URL: `https://customer.captain.taxi/voice/trip-status`
- Body: `trip_id` (string, required), `caller_phone` (system param)

### cancel_trip
- URL: `https://customer.captain.taxi/voice/cancel`
- Body: `trip_id` (required), `reason` (string), `caller_phone` (system param)

### get_fare_estimate
- URL: `https://customer.captain.taxi/voice/fare-estimate`
- Body: `pickup_address` (required), `dropoff_address` (required), `after_hours` (bool)

### log_complaint
- URL: `https://customer.captain.taxi/voice/complaint`
- Body: `description` (required), `severity` ("minor" | "serious"),
  `trip_id` (optional), `caller_phone` (system param)

### lookup_customer_bookings
- URL: `https://customer.captain.taxi/voice/lookup-bookings`
- Body: `customer_phone` (optional), `caller_phone` (system param)

Each endpoint returns `{"result": "<text to speak back to the caller>"}`.

## 4. Workspace post-call webhook

In the ElevenLabs **Workspace → Webhooks** settings:

- **URL:** `https://customer.captain.taxi/voice/post-call`
- **Secret:** the same `ELEVENLABS_WEBHOOK_SECRET` value
- ElevenLabs signs the request body with HMAC-SHA256 and sends it in the
  `ElevenLabs-Signature` header (`sha256=<hex>`); the handler verifies it.

## 5. Phone number

You can either:

- **Native ElevenLabs number** — buy a number in the ElevenLabs dashboard
  and attach the agent to it.
- **BYO Twilio number** — link your existing Saskatoon (306-242-0000) and
  Regina (306-775-2222) Twilio numbers via the ElevenLabs Twilio import.
  Your Twilio account stays the carrier; ElevenLabs only handles the
  media + agent.

## 6. Verify

With the stack up locally:

```bash
docker compose up -d
export ELEVENLABS_WEBHOOK_SECRET=<the-same-secret-you-configured>
python scripts/test_elevenlabs_bot.py
```

The script hits every voice endpoint and asserts a real trip lands in
dispatch with `booking_source=phone`.
