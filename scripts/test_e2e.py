#!/usr/bin/env python3
"""
Captain Taxi — End-to-End Test
================================
Tests the full trip flow plus all new dispatch features:
  1. Health checks
  2. Seed test driver (online, with GPS)
  3. Book via customer web chat → trip assigned
  4. Driver lifecycle: accept → arrive → pickup → complete
  5. Verify final trip state + fare
  6. Direct dispatch booking (priority + via + instructions)
  7. Pre-booking (scheduled_for in future)
  8. No-show flow (mark arrived → noshow)
  9. Dispatch stats & queue endpoints
  10. Cleanup

Prerequisites:
  - docker compose up (all services running)
  - pip install httpx

Run:
  python scripts/test_e2e.py
"""

import asyncio
import re
import sys
import time
import uuid
from datetime import datetime, timezone, timedelta

import httpx

# ── Service URLs ────────────────────────────────────────────────────────────
CUSTOMER_URL  = "http://localhost:8002"
DISPATCH_URL  = "http://localhost:8001"

# Downtown Saskatoon — driver seeded here so they're near the pickup
DRIVER_LAT = 52.1332
DRIVER_LNG = -106.6700

# Colour helpers
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"

passed = 0
failed = 0


def ok(msg: str):
    global passed
    passed += 1
    print(f"  {GREEN}✓{RESET}  {msg}")


def fail(msg: str):
    global failed
    failed += 1
    print(f"  {RED}✗{RESET}  {msg}")


def step(msg: str):
    print(f"\n{CYAN}▶ {msg}{RESET}")


def warn(msg: str):
    print(f"  {YELLOW}⚠{RESET}  {msg}")


# ── Helpers ─────────────────────────────────────────────────────────────────

async def check_health(client: httpx.AsyncClient) -> bool:
    step("1 / 10 — Health checks")
    all_ok = True
    for name, url in [("customer :8002", f"{CUSTOMER_URL}/health"),
                      ("dispatch :8001", f"{DISPATCH_URL}/health")]:
        try:
            r = await client.get(url, timeout=5)
            if r.status_code == 200:
                ok(f"{name} is up")
            else:
                fail(f"{name} returned HTTP {r.status_code}")
                all_ok = False
        except httpx.RequestError as e:
            fail(f"{name} unreachable — {e}")
            all_ok = False
    return all_ok


async def seed_driver(client: httpx.AsyncClient) -> dict | None:
    step("2 / 10 — Seed test driver")
    payload = {
        "name": "E2E Test Driver",
        "phone": "+15550000001",
        "city": "saskatoon",
        "vehicle_model": "Toyota Camry",
        "vehicle_plate": "TEST-001",
        "rating": 4.8,
        "is_active": True,
        "status": "online",
    }
    try:
        r = await client.post(f"{DISPATCH_URL}/driver", json=payload, timeout=10)
        if r.status_code == 201:
            driver = r.json()
            ok(f"Driver created: {driver['name']} ({driver['id'][:8]}…) status={driver['status']}")
            return driver
        else:
            fail(f"Driver creation failed: HTTP {r.status_code} — {r.text[:200]}")
            return None
    except httpx.RequestError as e:
        fail(f"Could not reach dispatch: {e}")
        return None


async def seed_driver_location(client: httpx.AsyncClient, driver_id: str) -> bool:
    step("3 / 10 — Register driver GPS (downtown Saskatoon)")
    try:
        r = await client.post(
            f"{DISPATCH_URL}/driver/me/location",
            params={"driver_id": driver_id},
            json={"lat": DRIVER_LAT, "lng": DRIVER_LNG},
            timeout=10,
        )
        if r.status_code == 200:
            ok(f"Driver location set to ({DRIVER_LAT}, {DRIVER_LNG})")
            return True
        else:
            fail(f"Location update failed: HTTP {r.status_code} — {r.text[:200]}")
            return False
    except httpx.RequestError as e:
        fail(f"Could not update driver location: {e}")
        return False


async def send_booking_chat(client: httpx.AsyncClient) -> tuple[str | None, str | None]:
    step("4 / 10 — Book via customer web chat")
    session_id = str(uuid.uuid4())
    message = (
        "Hi, I need a taxi please. "
        "My name is E2E Tester, phone +15550000099. "
        "Pickup from 224 Idylwyld Dr N, Saskatoon. "
        "Dropoff to Saskatoon City Hospital, 701 Queen St. "
        "It's for now, ASAP."
    )
    try:
        r = await client.post(
            f"{CUSTOMER_URL}/chat/message",
            json={"session_id": session_id, "message": message, "customer_phone": "+15550000099"},
            timeout=30,
        )
        if r.status_code != 200:
            fail(f"Chat endpoint returned HTTP {r.status_code} — {r.text[:300]}")
            return None, None

        reply = r.json().get("reply", "")
        print(f"\n     Claude replied:\n     {YELLOW}{reply[:400]}{RESET}")

        uuid_match = re.search(
            r'\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b',
            reply, re.IGNORECASE
        )
        trip_id = None
        if uuid_match:
            trip_id = uuid_match.group(1)
            ok(f"Booking confirmed — trip ID: {trip_id[:8]}…")
        else:
            warn("No trip UUID in reply — searching dispatch for the trip")

        return trip_id, session_id
    except httpx.RequestError as e:
        fail(f"Chat request failed: {e}")
        return None, None


async def wait_for_assignment(client: httpx.AsyncClient, trip_id: str, timeout: int = 15) -> dict | None:
    step(f"5 / 10 — Wait for dispatch assignment (up to {timeout}s)")
    deadline = time.time() + timeout
    last_status = None
    while time.time() < deadline:
        try:
            r = await client.get(f"{DISPATCH_URL}/dispatch/trip/{trip_id}", timeout=5)
            if r.status_code == 200:
                trip = r.json()
                status = trip.get("status")
                if status != last_status:
                    print(f"     status → {status}")
                    last_status = status
                if status == "assigned":
                    ok(f"Trip assigned to driver {trip.get('driver_id', '')[:8]}…")
                    ok(f"AI reasoning: {trip.get('ai_reasoning', '')[:80]}")
                    return trip
                elif status in ("cancelled", "completed"):
                    fail(f"Trip ended unexpectedly: '{status}'")
                    return None
        except httpx.RequestError:
            pass
        await asyncio.sleep(1)
    fail(f"Trip not assigned within {timeout}s (last status: {last_status})")
    return None


async def simulate_driver_lifecycle(client: httpx.AsyncClient, trip: dict) -> bool:
    step("6 / 10 — Simulate driver lifecycle (accept → arrive → pickup → complete)")
    trip_id   = trip["id"]
    driver_id = trip["driver_id"]

    steps = [
        ("accept",   f"{DISPATCH_URL}/driver/trip/{trip_id}/accept",   {"driver_id": driver_id}, "Driver accepted trip"),
        ("arrive",   f"{DISPATCH_URL}/driver/trip/{trip_id}/arrive",   {"driver_id": driver_id}, "Driver arrived at pickup"),
        ("pickup",   f"{DISPATCH_URL}/driver/trip/{trip_id}/pickup",   {"driver_id": driver_id}, "Trip started — passenger in vehicle"),
        ("complete", f"{DISPATCH_URL}/driver/trip/{trip_id}/complete", {"driver_id": driver_id, "fare_final": 18.50}, "Trip completed — $18.50"),
    ]

    all_ok = True
    for action, url, params, label in steps:
        try:
            r = await client.post(url, params=params, timeout=10)
            if r.status_code == 200:
                ok(label)
            else:
                fail(f"{action}: HTTP {r.status_code} — {r.text[:200]}")
                all_ok = False
                break
        except httpx.RequestError as e:
            fail(f"{action}: request error — {e}")
            all_ok = False
            break
        await asyncio.sleep(0.3)

    return all_ok


async def verify_final_state(client: httpx.AsyncClient, trip_id: str) -> bool:
    step("7 / 10 — Verify final trip state")
    try:
        r = await client.get(f"{DISPATCH_URL}/dispatch/trip/{trip_id}", timeout=5)
        if r.status_code != 200:
            fail(f"Could not fetch trip: HTTP {r.status_code}")
            return False
        trip = r.json()
        if trip.get("status") == "completed":
            ok("Trip status: completed")
        else:
            fail(f"Expected 'completed', got '{trip.get('status')}'")
            return False
        fare = trip.get("fare_final")
        if fare == 18.50:
            ok(f"Fare recorded: ${fare}")
        else:
            warn(f"Fare: {fare} (expected 18.50)")
        return True
    except httpx.RequestError as e:
        fail(f"Could not verify: {e}")
        return False


async def test_direct_booking(client: httpx.AsyncClient, driver_id: str) -> str | None:
    """Test 8a: Direct dispatch booking with priority + via + instructions."""
    step("8 / 10 — Direct booking (priority=high, via, instructions)")
    payload = {
        "customer_name": "Priority Tester",
        "customer_phone": "+15550000200",
        "customer_email": "priority@test.local",
        "pickup_address": "500 Victoria Ave, Regina, SK",
        "dropoff_address": "Airport, Regina SK",
        "via_address": "1000 Albert St, Regina",
        "city": "saskatoon",  # driver is in saskatoon
        "notes": "E2E priority test",
        "instructions": "Wait at front entrance, handicap accessible",
        "site": "Hospital",
        "priority": 1,
        "booking_source": "agent",
    }
    try:
        r = await client.post(f"{DISPATCH_URL}/dispatch/trip", json=payload, timeout=10)
        if r.status_code == 201:
            trip = r.json()
            trip_id = trip["id"]
            assert trip["priority"] == 1, f"Expected priority=1, got {trip['priority']}"
            assert trip["via_address"] == "1000 Albert St, Regina", "via_address not saved"
            assert trip["instructions"] == "Wait at front entrance, handicap accessible", "instructions not saved"
            assert trip["customer_email"] == "priority@test.local", "customer_email not saved"
            ok(f"Priority booking created: {trip_id[:8]}… priority={trip['priority']}")
            ok(f"Via: {trip['via_address']}")
            ok(f"Instructions: {trip['instructions']}")
            ok(f"Email: {trip['customer_email']}")
            return trip_id
        else:
            fail(f"Direct booking failed: HTTP {r.status_code} — {r.text[:300]}")
            return None
    except httpx.RequestError as e:
        fail(f"Direct booking request error: {e}")
        return None
    except AssertionError as e:
        fail(f"Field assertion failed: {e}")
        return None


async def test_prebooking(client: httpx.AsyncClient) -> str | None:
    """Test 8b: Pre-booking with scheduled_for in the future."""
    step("8b — Pre-booking (scheduled for 2 hours from now)")
    scheduled = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    payload = {
        "customer_name": "Pre-book Tester",
        "customer_phone": "+15550000300",
        "pickup_address": "221B Baker St, Saskatoon",
        "dropoff_address": "Market Mall, Saskatoon",
        "city": "saskatoon",
        "scheduled_for": scheduled,
        "priority": 0,
        "booking_source": "agent",
    }
    try:
        r = await client.post(f"{DISPATCH_URL}/dispatch/trip", json=payload, timeout=10)
        if r.status_code == 201:
            trip = r.json()
            trip_id = trip["id"]
            assert trip["status"] == "pending", f"Expected pending, got {trip['status']}"
            assert trip["scheduled_for"] is not None, "scheduled_for not saved"
            ok(f"Pre-booking created: {trip_id[:8]}… scheduled_for set")
            ok(f"Status still pending (not auto-assigned, correctly)")
            return trip_id
        else:
            fail(f"Pre-booking failed: HTTP {r.status_code} — {r.text[:300]}")
            return None
    except (httpx.RequestError, AssertionError) as e:
        fail(f"Pre-booking error: {e}")
        return None


async def test_noshow(client: httpx.AsyncClient, driver_id: str) -> bool:
    """Test 9: Create trip, assign to driver, mark no-show."""
    step("9 / 10 — No-show flow")
    # Create a new trip
    payload = {
        "customer_name": "NoShow Tester",
        "customer_phone": "+15550000400",
        "pickup_address": "Central Bus Terminal, Saskatoon",
        "dropoff_address": "Lakewood Civic Centre, Saskatoon",
        "city": "saskatoon",
        "booking_source": "agent",
    }
    try:
        r = await client.post(f"{DISPATCH_URL}/dispatch/trip", json=payload, timeout=10)
        if r.status_code != 201:
            fail(f"Could not create noshow trip: HTTP {r.status_code}")
            return False
        trip_id = r.json()["id"]
        ok(f"No-show trip created: {trip_id[:8]}…")

        # Wait for assignment (up to 10s)
        deadline = time.time() + 10
        assigned = False
        while time.time() < deadline:
            r2 = await client.get(f"{DISPATCH_URL}/dispatch/trip/{trip_id}", timeout=5)
            if r2.status_code == 200 and r2.json().get("status") == "assigned":
                assigned = True
                break
            await asyncio.sleep(1)

        if not assigned:
            # Mark noshow even from pending
            warn("Trip not assigned — marking no-show from pending state")

        r3 = await client.post(f"{DISPATCH_URL}/dispatch/trip/{trip_id}/noshow", timeout=10)
        if r3.status_code == 200:
            noshow_trip = r3.json()
            assert noshow_trip["status"] == "noshow", f"Expected noshow, got {noshow_trip['status']}"
            assert noshow_trip["noshow_at"] is not None, "noshow_at not set"
            ok(f"Trip marked as no-show, noshow_at={noshow_trip['noshow_at'][:19]}")
            return True
        else:
            fail(f"noshow endpoint returned HTTP {r3.status_code} — {r3.text[:200]}")
            return False
    except (httpx.RequestError, AssertionError) as e:
        fail(f"No-show test error: {e}")
        return False


async def test_stats_and_queue(client: httpx.AsyncClient) -> bool:
    """Test 10: Dispatch stats and queue endpoints."""
    step("10 / 10 — Stats and queue endpoints")
    all_ok = True

    # Stats
    try:
        r = await client.get(f"{DISPATCH_URL}/dashboard/stats?city=saskatoon", timeout=10)
        if r.status_code == 200:
            stats = r.json()
            assert "completed_trips" in stats
            assert "active_drivers" in stats
            assert "pending_trips" in stats
            ok(f"Stats OK — completed={stats['completed_trips']}, active_drivers={stats['active_drivers']}, pending={stats['pending_trips']}")
        else:
            fail(f"Stats endpoint: HTTP {r.status_code}")
            all_ok = False
    except (httpx.RequestError, AssertionError) as e:
        fail(f"Stats error: {e}")
        all_ok = False

    # Queue
    try:
        r = await client.get(f"{DISPATCH_URL}/dashboard/queue?city=saskatoon&history_hours=4", timeout=10)
        if r.status_code == 200:
            queue = r.json()
            required_keys = {"dispatch", "pre_booked", "booked", "in_progress", "completed", "cancelled", "noshow"}
            missing = required_keys - set(queue.keys())
            if missing:
                fail(f"Queue missing tabs: {missing}")
                all_ok = False
            else:
                ok(f"Queue OK — tabs: {list(queue.keys())}")
                ok(f"  dispatch={len(queue['dispatch'])}, pre_booked={len(queue['pre_booked'])}, "
                   f"completed={len(queue['completed'])}, noshow={len(queue['noshow'])}")
        else:
            fail(f"Queue endpoint: HTTP {r.status_code}")
            all_ok = False
    except (httpx.RequestError, AssertionError) as e:
        fail(f"Queue error: {e}")
        all_ok = False

    # Map
    try:
        r = await client.get(f"{DISPATCH_URL}/dashboard/map?city=saskatoon", timeout=10)
        if r.status_code == 200:
            data = r.json()
            assert "drivers" in data and "trips" in data
            ok(f"Map OK — {len(data['drivers'])} driver(s), {len(data['trips'])} active trip(s)")
        else:
            fail(f"Map endpoint: HTTP {r.status_code}")
            all_ok = False
    except (httpx.RequestError, AssertionError) as e:
        fail(f"Map error: {e}")
        all_ok = False

    return all_ok


async def test_driver_statuses(client: httpx.AsyncClient, driver_id: str) -> bool:
    """Bonus: Test new driver statuses (parked, dropping, bidding)."""
    step("Bonus — New driver statuses (parked / dropping / bidding)")
    all_ok = True
    for status in ("parked", "dropping", "bidding", "online"):
        try:
            r = await client.post(
                f"{DISPATCH_URL}/driver/me/status",
                params={"driver_id": driver_id},
                json={"status": status},
                timeout=5,
            )
            if r.status_code == 200:
                returned = r.json().get("status")
                if returned == status:
                    ok(f"Status → {status}")
                else:
                    fail(f"Set {status} but got {returned}")
                    all_ok = False
            else:
                fail(f"Status {status}: HTTP {r.status_code} — {r.text[:100]}")
                all_ok = False
        except httpx.RequestError as e:
            fail(f"Status {status} request error: {e}")
            all_ok = False
    return all_ok


async def cleanup(client: httpx.AsyncClient, driver_id: str, trip_ids: list[str]):
    print(f"\n{CYAN}▶ Cleanup{RESET}")
    for trip_id in trip_ids:
        try:
            r = await client.get(f"{DISPATCH_URL}/dispatch/trip/{trip_id}", timeout=5)
            if r.status_code == 200:
                status = r.json().get("status")
                if status not in ("completed", "cancelled", "noshow"):
                    await client.post(
                        f"{DISPATCH_URL}/dispatch/trip/{trip_id}/cancel",
                        json={"reason": "E2E test cleanup"},
                        timeout=5,
                    )
                    print(f"  Cancelled trip {trip_id[:8]}…")
        except httpx.RequestError:
            pass

    try:
        r = await client.patch(
            f"{DISPATCH_URL}/driver/{driver_id}",
            json={"is_active": False},
            timeout=5,
        )
        if r.status_code == 200:
            print(f"  Deactivated test driver {driver_id[:8]}…")
    except httpx.RequestError:
        pass


# ── Main ────────────────────────────────────────────────────────────────────

async def main():
    print(f"\n{CYAN}{'=' * 60}")
    print("  Captain Taxi — End-to-End Test  (v2)")
    print(f"{'=' * 60}{RESET}\n")

    driver = None
    trip_ids: list[str] = []
    chat_trip_id: str | None = None

    async with httpx.AsyncClient() as client:
        # 1. Health
        if not await check_health(client):
            print(f"\n{RED}Services not running. Start with: docker compose up{RESET}")
            sys.exit(1)

        # 2. Seed driver
        driver = await seed_driver(client)
        if not driver:
            sys.exit(1)
        driver_id = driver["id"]

        # 3. GPS
        if not await seed_driver_location(client, driver_id):
            await cleanup(client, driver_id, [])
            sys.exit(1)

        # 4. Chat booking
        chat_trip_id, _ = await send_booking_chat(client)

        if not chat_trip_id:
            warn("Searching dispatch for pending trip from +15550000099…")
            try:
                r = await client.get(f"{DISPATCH_URL}/dispatch/trips?limit=5", timeout=5)
                if r.status_code == 200:
                    for t in r.json():
                        if t.get("customer_phone") == "+15550000099":
                            chat_trip_id = t["id"]
                            ok(f"Found trip via dispatch: {chat_trip_id[:8]}…")
                            break
            except httpx.RequestError:
                pass

        if not chat_trip_id:
            fail("Could not obtain a trip ID — aborting")
            await cleanup(client, driver_id, [])
            sys.exit(1)

        trip_ids.append(chat_trip_id)

        # 5. Wait for assignment
        assigned_trip = await wait_for_assignment(client, chat_trip_id)
        if not assigned_trip:
            await cleanup(client, driver_id, trip_ids)
            sys.exit(1)

        # 6. Driver lifecycle
        await simulate_driver_lifecycle(client, assigned_trip)

        # 7. Final state
        await verify_final_state(client, chat_trip_id)

        # 8. Direct booking
        direct_trip_id = await test_direct_booking(client, driver_id)
        if direct_trip_id:
            trip_ids.append(direct_trip_id)

        # 8b. Pre-booking
        pre_trip_id = await test_prebooking(client)
        if pre_trip_id:
            trip_ids.append(pre_trip_id)

        # 9. No-show
        await test_noshow(client, driver_id)

        # 10. Stats + queue + map
        await test_stats_and_queue(client)

        # Bonus: driver statuses
        await test_driver_statuses(client, driver_id)

        # Cleanup
        await cleanup(client, driver_id, trip_ids)

    # ── Summary ──────────────────────────────────────────────────────────────
    total = passed + failed
    print(f"\n{CYAN}{'=' * 60}{RESET}")
    if failed == 0:
        print(f"{GREEN}  ALL {total} CHECKS PASSED{RESET}")
    else:
        print(f"{RED}  {failed} FAILED / {total} TOTAL{RESET}")
    print(f"{CYAN}{'=' * 60}{RESET}\n")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
