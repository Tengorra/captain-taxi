#!/usr/bin/env python3
"""
Captain Taxi — Vapi phone-bot simulator
=========================================
Simulates a Vapi tool-call webhook against the running customer service.
Lets you verify the phone-call → dispatch flow without a real phone call.

The script:
  1. POSTs a fake `tool-calls` event (create_booking) to /webhook/vapi/call
  2. Asserts a 200 with a `results` array containing a booking confirmation
  3. Extracts the trip ID from the result text
  4. Confirms the trip exists in dispatch with booking_source=phone
  5. POSTs a fake `end-of-call-report` event and verifies it's accepted

Prerequisites:
  docker compose up   (customer service on :8002, dispatch on :8001)

Run:
  python scripts/test_vapi_bot.py
"""

import asyncio
import json
import re
import sys
import uuid

import httpx

CUSTOMER_URL = "http://localhost:8002"
DISPATCH_URL = "http://localhost:8001"

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


CALLER_PHONE = "+15551239999"


def _tool_calls_event() -> dict:
    """Shape of a Vapi 'tool-calls' message."""
    return {
        "message": {
            "type": "tool-calls",
            "call": {"customer": {"number": CALLER_PHONE}},
            "toolCalls": [
                {
                    "id": str(uuid.uuid4()),
                    "function": {
                        "name": "create_booking",
                        "arguments": {
                            "pickup_address": "224 Idylwyld Dr N, Saskatoon",
                            "dropoff_address": "Saskatoon City Hospital, 701 Queen St",
                            "customer_name": "Phone Bot Tester",
                            "customer_phone": CALLER_PHONE,
                            "num_passengers": 1,
                            "pickup_time": "ASAP",
                            "notes": "via vapi simulator",
                            "city": "saskatoon",
                        },
                    },
                }
            ],
        }
    }


def _end_of_call_event() -> dict:
    return {
        "message": {
            "type": "end-of-call-report",
            "summary": "Customer booked a taxi from Idylwyld to City Hospital.",
            "call": {
                "customer": {"number": CALLER_PHONE},
                "startedAt": "2026-05-18T10:00:00Z",
                "endedAt": "2026-05-18T10:02:30Z",
            },
        }
    }


async def main():
    print(f"{CYAN}Captain Taxi — Vapi Phone-Bot Simulator{RESET}")
    print(f"{CYAN}{'=' * 45}{RESET}")

    async with httpx.AsyncClient(timeout=30) as client:
        # ── 0. Health checks ──────────────────────────────────────────
        step("1 / 4 — Health check (customer + dispatch)")
        try:
            r1 = await client.get(f"{CUSTOMER_URL}/health")
            r2 = await client.get(f"{DISPATCH_URL}/health")
        except httpx.RequestError as e:
            bad(f"Cannot reach services: {e}")
            sys.exit(1)
        if r1.status_code == 200 and r2.status_code == 200:
            ok("Both services healthy")
        else:
            bad(f"Health checks failed: customer={r1.status_code} dispatch={r2.status_code}")
            sys.exit(1)

        # ── 1. Simulate the tool-calls webhook ────────────────────────
        step("2 / 4 — POST simulated Vapi tool-calls (create_booking)")
        payload = _tool_calls_event()
        r = await client.post(f"{CUSTOMER_URL}/webhook/vapi/call", json=payload)
        if r.status_code != 200:
            bad(f"Webhook returned HTTP {r.status_code} — {r.text[:200]}")
            sys.exit(1)
        body = r.json()
        results = body.get("results") or []
        if not results:
            bad(f"Webhook returned no results: {body}")
            sys.exit(1)
        result_text = results[0].get("result", "")
        print(f"     tool result: {result_text[:200]}")
        ok("Webhook accepted tool call and returned a result")

        # Extract trip ID
        uuid_match = re.search(
            r"\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b",
            result_text, re.IGNORECASE,
        )
        if not uuid_match:
            bad("No trip UUID found in result text")
            sys.exit(1)
        trip_id = uuid_match.group(1)
        ok(f"Trip ID extracted: {trip_id[:8]}…")

        # ── 2. Verify trip in dispatch with booking_source=phone ─────
        step("3 / 4 — Verify trip lands in dispatch with booking_source=phone")
        r = await client.get(f"{DISPATCH_URL}/dispatch/trip/{trip_id}")
        if r.status_code != 200:
            bad(f"Dispatch lookup failed: HTTP {r.status_code} — {r.text[:200]}")
            sys.exit(1)
        trip = r.json()
        if trip.get("booking_source") != "phone":
            bad(f"booking_source={trip.get('booking_source')} (expected 'phone')")
        else:
            ok(f"booking_source='phone' ✓ — status={trip['status']}, city={trip['city']}")

        if trip.get("customer_phone") != CALLER_PHONE:
            bad(f"customer_phone={trip.get('customer_phone')} (expected {CALLER_PHONE})")
        else:
            ok(f"customer_phone propagated: {CALLER_PHONE}")

        # ── 3. Also confirm the phone filter on /dispatch/trips works
        r = await client.get(
            f"{DISPATCH_URL}/dispatch/trips",
            params={"booking_source": "phone", "limit": 10},
        )
        if r.status_code == 200 and any(t["id"] == trip_id for t in r.json()):
            ok("Trip appears in GET /dispatch/trips?booking_source=phone")
        else:
            bad("Trip missing from booking_source=phone filter")

        # ── 4. Simulate end-of-call report ────────────────────────────
        step("4 / 4 — POST simulated end-of-call-report")
        r = await client.post(f"{CUSTOMER_URL}/webhook/vapi/call", json=_end_of_call_event())
        if r.status_code == 200 and r.json().get("status") == "ok":
            ok("end-of-call-report accepted")
        else:
            bad(f"end-of-call HTTP {r.status_code} — {r.text[:200]}")

        # ── Cleanup ───────────────────────────────────────────────────
        await client.post(
            f"{DISPATCH_URL}/dispatch/trip/{trip_id}/cancel",
            json={"reason": "vapi simulator cleanup"},
        )

    print(f"\n{CYAN}{'=' * 45}{RESET}")
    print(f"  Passed: {GREEN}{passed}{RESET}")
    print(f"  Failed: {RED}{failed}{RESET}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
