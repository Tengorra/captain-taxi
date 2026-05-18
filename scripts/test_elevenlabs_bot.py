#!/usr/bin/env python3
"""
Captain Taxi — ElevenLabs Agents simulator
============================================
Simulates each tool that the ElevenLabs voice agent will call. Useful
because, unlike Vapi, ElevenLabs hits a separate endpoint per tool,
so we hit each one directly with the JSON the dashboard tool config
would emit.

Covers:
  1. Health
  2. POST /voice/booking          (create_booking tool)
  3. POST /voice/trip-status      (get_trip_status tool)
  4. POST /voice/cancel           (cancel_trip tool)
  5. POST /voice/fare-estimate    (get_fare_estimate tool)
  6. POST /voice/complaint        (log_complaint tool)
  7. POST /voice/lookup-bookings  (lookup_customer_bookings tool)
  8. POST /voice/post-call        (workspace post-call webhook)

Run:
  docker compose up -d
  python scripts/test_elevenlabs_bot.py

If ELEVENLABS_WEBHOOK_SECRET is set in the customer service, export it
in this shell so the simulator can sign the requests:
  export ELEVENLABS_WEBHOOK_SECRET=...
"""

import asyncio
import hashlib
import hmac
import json
import os
import re
import sys
import uuid

import httpx

CUSTOMER_URL = "http://localhost:8002"
DISPATCH_URL = "http://localhost:8001"

SECRET = os.environ.get("ELEVENLABS_WEBHOOK_SECRET", "")
AUTH_HEADER = os.environ.get("CAPTAIN_AUTH_HEADER", "X-Captain-Auth")
CALLER_PHONE = "+15557779999"

GREEN, RED, CYAN, RESET = "\033[92m", "\033[91m", "\033[96m", "\033[0m"
passed = failed = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  {GREEN}✓{RESET} {msg}")


def bad(msg):
    global failed
    failed += 1
    print(f"  {RED}✗{RESET} {msg}")


def step(msg):
    print(f"\n{CYAN}▸ {msg}{RESET}")


def _auth_headers():
    return {AUTH_HEADER: SECRET} if SECRET else {}


async def post(client, path, json_body, extra_headers=None):
    headers = _auth_headers()
    if extra_headers:
        headers.update(extra_headers)
    return await client.post(f"{CUSTOMER_URL}{path}", json=json_body, headers=headers)


async def main():
    print(f"{CYAN}Captain Taxi — ElevenLabs Agents Simulator{RESET}")
    print(f"{CYAN}{'=' * 50}{RESET}")
    if not SECRET:
        print("  (no ELEVENLABS_WEBHOOK_SECRET in env — auth header omitted)")

    async with httpx.AsyncClient(timeout=30) as client:
        step("1 / 8 — Health")
        try:
            h1 = (await client.get(f"{CUSTOMER_URL}/health")).status_code
            h2 = (await client.get(f"{DISPATCH_URL}/health")).status_code
        except httpx.RequestError as e:
            bad(f"Cannot reach services: {e}")
            sys.exit(1)
        if h1 == 200 and h2 == 200:
            ok(f"customer={h1} dispatch={h2}")
        else:
            bad(f"customer={h1} dispatch={h2}")
            sys.exit(1)

        # ── 2. Booking ────────────────────────────────────────────────
        step("2 / 8 — POST /voice/booking (create_booking tool)")
        r = await post(client, "/voice/booking", {
            "pickup_address": "224 Idylwyld Dr N, Saskatoon",
            "dropoff_address": "Saskatoon City Hospital, 701 Queen St",
            "customer_name": "ElevenLabs Tester",
            "customer_phone": CALLER_PHONE,
            "caller_phone": CALLER_PHONE,
            "num_passengers": 1,
            "pickup_time": "ASAP",
            "notes": "via elevenlabs simulator",
            "city": "saskatoon",
            "conversation_id": str(uuid.uuid4()),
        })
        if r.status_code != 200:
            bad(f"booking: HTTP {r.status_code} — {r.text[:200]}")
            sys.exit(1)
        body = r.json()
        spoken = body.get("result", "")
        trip_id = body.get("trip_id")
        print(f"     spoken: {spoken[:200]}")
        if not trip_id:
            bad("no trip_id in response")
            sys.exit(1)
        ok(f"booking confirmed, trip_id={trip_id[:8]}…")

        # Verify it landed in dispatch with booking_source=phone
        d = await client.get(f"{DISPATCH_URL}/dispatch/trip/{trip_id}")
        if d.status_code == 200 and d.json().get("booking_source") == "phone":
            ok("dispatch shows booking_source=phone")
        else:
            bad(f"dispatch verify failed: {d.status_code} {d.text[:120]}")

        # ── 3. Trip status ────────────────────────────────────────────
        step("3 / 8 — POST /voice/trip-status")
        r = await post(client, "/voice/trip-status", {"trip_id": trip_id, "caller_phone": CALLER_PHONE})
        if r.status_code == 200 and "status" in r.json().get("result", "").lower():
            ok(f"status spoken: {r.json()['result'][:120]}")
        else:
            bad(f"trip-status: {r.status_code} {r.text[:120]}")

        # ── 4. Fare estimate ──────────────────────────────────────────
        step("4 / 8 — POST /voice/fare-estimate")
        r = await post(client, "/voice/fare-estimate", {
            "pickup_address": "downtown saskatoon",
            "dropoff_address": "saskatoon airport YXE",
            "after_hours": False,
        })
        if r.status_code == 200 and "dollars" in r.json().get("result", "").lower():
            ok(f"estimate: {r.json()['result'][:120]}")
        else:
            bad(f"fare-estimate: {r.status_code} {r.text[:120]}")

        # ── 5. Lookup bookings ────────────────────────────────────────
        step("5 / 8 — POST /voice/lookup-bookings")
        r = await post(client, "/voice/lookup-bookings", {"caller_phone": CALLER_PHONE})
        if r.status_code == 200:
            ok(f"lookup spoken: {r.json().get('result', '')[:120]}")
        else:
            bad(f"lookup: {r.status_code} {r.text[:120]}")

        # ── 6. Complaint (minor) ──────────────────────────────────────
        step("6 / 8 — POST /voice/complaint (minor)")
        r = await post(client, "/voice/complaint", {
            "description": "Driver took a longer route than necessary",
            "severity": "minor",
            "trip_id": trip_id,
            "caller_phone": CALLER_PHONE,
        })
        if r.status_code == 200 and "reference" in r.json().get("result", "").lower():
            ok(f"minor complaint logged: {r.json()['result'][:120]}")
        else:
            bad(f"complaint: {r.status_code} {r.text[:120]}")

        # ── 7. Cancel ─────────────────────────────────────────────────
        step("7 / 8 — POST /voice/cancel")
        r = await post(client, "/voice/cancel", {
            "trip_id": trip_id,
            "reason": "simulator cleanup",
            "caller_phone": CALLER_PHONE,
        })
        if r.status_code == 200 and "cancel" in r.json().get("result", "").lower():
            ok(f"cancel spoken: {r.json()['result'][:120]}")
        else:
            bad(f"cancel: {r.status_code} {r.text[:120]}")

        # ── 8. Post-call webhook ──────────────────────────────────────
        step("8 / 8 — POST /voice/post-call (workspace webhook)")
        post_call_body = {
            "data": {
                "conversation_id": str(uuid.uuid4()),
                "metadata": {"phone_call": {"external_number": CALLER_PHONE}},
                "analysis": {"transcript_summary": "Caller booked a taxi from Idylwyld."},
            }
        }
        raw = json.dumps(post_call_body).encode()
        headers = {"Content-Type": "application/json"}
        if SECRET:
            sig = hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
            headers["ElevenLabs-Signature"] = f"sha256={sig}"
        r = await client.post(f"{CUSTOMER_URL}/voice/post-call", content=raw, headers=headers)
        if r.status_code == 200 and r.json().get("status") == "ok":
            ok("post-call accepted")
        else:
            bad(f"post-call: {r.status_code} {r.text[:200]}")

    print(f"\n{CYAN}{'=' * 50}{RESET}")
    print(f"  Passed: {GREEN}{passed}{RESET}")
    print(f"  Failed: {RED}{failed}{RESET}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
