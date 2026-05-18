# Captain Taxi — BOT (voice dispatcher)

ElevenLabs Conversational AI takes the inbound taxi call; this FastAPI
service exposes the webhook, the client tools the agent calls, a live
WebSocket log stream for the dashboard, and a warm-transfer path to a
human dispatcher.

Service runs on **port 8007**.

## What it does

| Concern | How |
|---|---|
| Hear the caller | ElevenLabs handles speech-to-text + turn-taking |
| Talk back | ElevenLabs TTS (voice picked in their dashboard) |
| Book the trip | Calls our `book_trip` tool → `POST dispatch:8001/dispatch/trip` with `booking_source="bot"` |
| Live logs | Every event published to Redis (`bot:call_logs`) and fanned out over `ws://bot:8007/calls/stream` |
| History replay | Last 1h of events per call cached in Redis (`bot:call_history:<call_id>`) |
| Warm-transfer | `twilio.calls(CallSid).update(twiml=<Response><Dial>HUMAN</Dial></Response>)` |

## Escalation triggers

The bot transfers to a human dispatcher automatically when:

1. **Phrase match** — caller says any of `transfer_trigger_phrases` in
   `bot/config.py` (defaults: "speak to a human", "real person",
   "manager", "supervisor", "complaint", "this is ridiculous").
2. **Repeated tool failures** — `transfer_after_tool_failures`
   consecutive failures on the same call (default 2).
3. **Manual** — dashboard "Transfer to human" button → `POST
   /calls/{call_id}/transfer`.

The ElevenLabs system prompt is also told to call `transfer_to_human`
on abuse, distress, or out-of-scope requests; that triggers the same
Twilio redirect.

## One-time setup

1. **`.env`** — set:
   - `ELEVENLABS_API_KEY`, `ELEVENLABS_AGENT_ID`, `ELEVENLABS_WEBHOOK_SECRET`
   - `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`
   - Optionally `HUMAN_DISPATCHER_SASKATOON`, `HUMAN_DISPATCHER_REGINA`
   (See `.env.example` for the full block.)

2. **ElevenLabs agent** — in the ElevenLabs dashboard, create a
   Conversational AI agent. Copy the prompt + 4 tool schemas from
   `bot/elevenlabs_agent.json` and point its webhook at:
   ```
   https://admin.captaintaxi.ca/webhook/elevenlabs/call
   ```
   Set the webhook signing secret to the same value as
   `ELEVENLABS_WEBHOOK_SECRET`.

3. **Twilio numbers** — point the public taxi lines
   (`+13062420000` Saskatoon, `+13067752222` Regina) at the
   ElevenLabs SIP trunk for the agent above. Twilio's call passes
   `CallSid` to ElevenLabs, which forwards it in tool-call payloads
   so warm-transfers can target the live call.

4. **Bring it up** — `docker compose up -d bot` (already wired in
   `docker-compose.yml` and `nginx.conf`).

## Endpoints

| Method | Path | Use |
|---|---|---|
| `POST` | `/webhook/elevenlabs/call` | ElevenLabs webhook — agent → bot |
| `GET`  | `/calls/{call_id}/history` | Replay events for one call |
| `POST` | `/calls/{call_id}/transfer` | Manual warm-transfer |
| `WS`   | `/calls/stream[?call_id=]` | Live event stream (dashboard) |
| `GET`  | `/health` | Health check |

Nginx exposes these as:

| External | Internal |
|---|---|
| `POST /webhook/elevenlabs/call` | bot:8007 |
| `GET/POST /api/bot/...` | bot:8007 |
| `WS /ws/calls/stream` | bot:8007 |

## Live event types

Every event the dashboard sees has the shape:

```json
{ "call_id": "abc...", "event": "user_message", "ts": 1715972400.0, "data": { ... } }
```

| Event | When | `data` keys |
|---|---|---|
| `call_started` | Inbound call connected | `from` |
| `user_message` | Caller utterance | `text` |
| `assistant_message` | Bot reply | `text` |
| `tool_call` | Bot invoking a client tool | `tool`, `args` |
| `tool_result` | Tool succeeded | `tool`, `result` |
| `tool_error` | Tool failed | `tool`, `error`, `consecutive_failures` |
| `trip_booked` | `book_trip` succeeded | `trip_id`, `city` |
| `auto_transfer` | Phrase- or failure-triggered transfer | `to`, `reason` |
| `manual_transfer` | Dashboard transfer | `to`, `reason` |
| `transferred_to_human` | Tool-driven transfer | `to`, `reason` |
| `call_ended` | Call hung up | `summary`, `duration_s` |

## Testing

The bot section of `scripts/test_e2e.py` simulates the full webhook
lifecycle (call.started → tool_call book_trip → call.ended) against a
running stack — no ElevenLabs subscription needed for that test. It
skips silently when `bot:8007` is down.

Unit tests for the pure helpers (difficulty heuristics, dispatch URL
inference) live in `bot/tests/` and run with `pytest bot/tests/`.

## Layout

```
bot/
├── main.py                # FastAPI app
├── config.py              # Settings (ElevenLabs + Twilio + heuristics)
├── elevenlabs_agent.json  # Copy-paste this into the ElevenLabs UI
├── routers/
│   ├── elevenlabs.py      # /webhook/elevenlabs/call
│   ├── calls.py           # /calls/{id}/history, /calls/{id}/transfer
│   ├── logs.py            # /calls/stream WebSocket
│   └── health.py
├── services/
│   ├── dispatch_client.py # POSTs trips to dispatch:8001
│   ├── log_stream.py      # Redis pub/sub broker + history
│   ├── transfer.py        # Twilio call.update TwiML redirect
│   └── difficulty.py      # Phrase + failure-count heuristics
└── tests/
    ├── test_difficulty.py
    └── test_dispatch_client.py
```
