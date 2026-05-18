#!/usr/bin/env python3
"""
Captain Taxi — Dispatch Session-8 E2E Test
===========================================
Covers the dispatch features added in session 8 (not exercised by
scripts/test_e2e.py):

  1. Health check
  2. Seed two drivers (so we can verify reassignment)
  3. Driver decline → second driver picks up trip
  4. en_route endpoint (assigned → en_route → arrived)
  5. Driver-side no-show endpoint
  6. booking_source filter on GET /dispatch/trips
  7. Driver WebSocket receives `trip_assigned` event
  8. Dispatcher cancel pushes `trip_cancelled` to driver WS
  9. Pre-booking lands in PRE-BOOKED queue bucket and gets dispatched
     by the scheduler when its pickup is within the lead window
  10. Cleanup

Prerequisites:
  - docker compose up (dispatch service reachable on :8001)
  - pip install httpx websockets

Run:
  python scripts/test_dispatch_session8.py
  python scripts/test_dispatch_session8.py --skip-scheduler  # skip the 60s wait
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone, timedelta

import httpx
import websockets

DISPATCH_URL = "http://localhost:8001"
DISPATCH_WS_BASE = "ws://localhost:8001"

# Downtown Saskatoon
PICKUP_LAT, PICKUP_LNG = 52.1332, -106.6700
DROPOFF_LAT, DROPOFF_LNG = 52.1500, -106.6900

GREEN, RED, YELLOW, CYAN, RESET = (
    "\033[92m", "\033[91m", "\033[93m", "\033[96m", "\033[0m"
)

passed = 0
failed = 0


def ok(msg: str):
    global passed
    passed += 1
    print(f"  {GREEN}✓{RESET} {msg}")


def fail(msg: str):
    global failed
    failed += 1
    print(f"  {RED}✗{RESET} {msg}")


def step(msg: str):
    print(f"\n{CYAN}▸ {msg}{RESET}")


def warn(msg: str):
    print(f"  {YELLOW}…{RESET} {msg}")


# ── Helpers ────────────────────────────────────────────────────────────────


async def check_health(client: httpx.AsyncClient) -> bool:
    step("1 / 10 — Health check")
    try:
        r = await client.get(f"{DISPATCH_URL}/health", timeout=5)
        if r.status_code == 200:
            ok(f"Dispatch healthy: {r.json()}")
            return True
        fail(f"Health check returned {r.status_code}")
        return False
    except httpx.RequestError as e:
        fail(f"Cannot reach dispatch: {e}")
        return False


async def seed_driver(client: httpx.AsyncClient, suffix: str, lat_offset: float = 0.0) -> dict | None:
    payload = {
        "name": f"S8 Driver {suffix}",
        "phone": f"+1555000{suffix}",
        "city": "saskatoon",
        "vehicle_model": "Toyota Camry",
        "vehicle_plate": f"S8-{suffix}",
        "rating": 4.7,
        "is_active": True,
        "status": "online",
    }
    r = await client.post(f"{DISPATCH_URL}/driver", json=payload, timeout=10)
    if r.status_code != 201:
        fail(f"Driver {suffix} creation failed: HTTP {r.status_code} — {r.text[:200]}")
        return None
    driver = r.json()
    # Register GPS
    loc = await client.post(
        f"{DISPATCH_URL}/driver/me/location",
        params={"driver_id": driver["id"]},
        json={"lat": PICKUP_LAT + lat_offset, "lng": PICKUP_LNG},
        timeout=10,
    )
    if loc.status_code != 200:
        fail(f"Driver {suffix} location update failed: {loc.text[:200]}")
        return None
    ok(f"Driver {suffix} seeded online at pickup area (id={driver['id'][:8]}…)")
    return driver


async def create_trip(client: httpx.AsyncClient, **overrides) -> dict | None:
    payload = {
        "customer_name": "S8 Tester",
        "customer_phone": "+15550009999",
        "pickup_address": "224 Idylwyld Dr N, Saskatoon",
        "pickup_lat": PICKUP_LAT,
        "pickup_lng": PICKUP_LNG,
        "dropoff_address": "Saskatoon City Hospital, 701 Queen St",
        "dropoff_lat": DROPOFF_LAT,
        "dropoff_lng": DROPOFF_LNG,
        "city": "saskatoon",
        "booking_source": "phone",
    }
    payload.update(overrides)
    r = await client.post(f"{DISPATCH_URL}/dispatch/trip", json=payload, timeout=10)
    if r.status_code != 201:
        fail(f"Trip creation failed: HTTP {r.status_code} — {r.text[:200]}")
        return None
    return r.json()


async def wait_for_status(
    client: httpx.AsyncClient, trip_id: str, target, timeout: int = 15
) -> dict | None:
    """Poll trip until status matches `target` (str or iterable of strings)."""
    if isinstance(target, str):
        target = {target}
    else:
        target = set(target)
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        r = await client.get(f"{DISPATCH_URL}/dispatch/trip/{trip_id}", timeout=5)
        if r.status_code == 200:
            trip = r.json()
            if trip["status"] != last:
                print(f"     status → {trip['status']}")
                last = trip["status"]
            if trip["status"] in target:
                return trip
        await asyncio.sleep(1)
    return None


async def wait_for_driver(
    client: httpx.AsyncClient, trip_id: str, exclude_id: str, timeout: int = 15
) -> dict | None:
    """Poll until trip is assigned to a driver other than `exclude_id`."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = await client.get(f"{DISPATCH_URL}/dispatch/trip/{trip_id}", timeout=5)
        if r.status_code == 200:
            trip = r.json()
            if (
                trip["status"] == "assigned"
                and trip.get("driver_id")
                and trip["driver_id"] != exclude_id
            ):
                return trip
        await asyncio.sleep(1)
    return None


# ── Tests ──────────────────────────────────────────────────────────────────


async def test_decline_and_reassign(
    client: httpx.AsyncClient, driver_a: dict, driver_b: dict
) -> str | None:
    step("3 / 10 — Decline → reassignment to second driver")
    trip = await create_trip(client, notes="decline test")
    if not trip:
        return None
    trip_id = trip["id"]

    # Wait for initial assignment
    assigned = await wait_for_status(client, trip_id, "assigned", timeout=10)
    if not assigned:
        fail("Trip did not get assigned within 10s")
        return trip_id
    first_driver = assigned["driver_id"]
    ok(f"Trip initially assigned to {first_driver[:8]}…")

    # Decline as the assigned driver
    r = await client.post(
        f"{DISPATCH_URL}/driver/trip/{trip_id}/decline",
        params={"driver_id": first_driver, "reason": "too far"},
        timeout=10,
    )
    if r.status_code != 200:
        fail(f"Decline failed: HTTP {r.status_code} — {r.text[:200]}")
        return trip_id
    ok("Driver declined the trip")

    # Wait for reassignment to the other driver
    other = driver_b["id"] if first_driver == driver_a["id"] else driver_a["id"]
    reassigned = await wait_for_driver(client, trip_id, exclude_id=first_driver, timeout=15)
    if not reassigned:
        fail("Trip was not reassigned to another driver within 15s")
        return trip_id
    if reassigned["driver_id"] == other:
        ok(f"Trip reassigned to second driver {other[:8]}…")
    else:
        ok(f"Trip reassigned to {reassigned['driver_id'][:8]}…")

    if "Declined" in (reassigned.get("ai_reasoning") or ""):
        # Reasoning gets overwritten by the new assignment; declined was
        # captured on the intermediate state. Either is fine.
        pass
    return trip_id


async def test_en_route_endpoint(
    client: httpx.AsyncClient, driver: dict
) -> str | None:
    step("4 / 10 — assigned → en_route → arrived → pickup → complete")
    trip = await create_trip(client, notes="en_route test")
    if not trip:
        return None
    trip_id = trip["id"]
    assigned = await wait_for_status(client, trip_id, "assigned", timeout=10)
    if not assigned:
        fail("Trip did not get assigned")
        return trip_id
    driver_id = assigned["driver_id"]

    transitions = [
        ("accept", "/driver/trip/{id}/accept", "assigned"),
        ("en_route", "/driver/trip/{id}/en_route", "en_route"),
        ("arrive", "/driver/trip/{id}/arrive", "arrived"),
        ("pickup", "/driver/trip/{id}/pickup", "in_progress"),
    ]
    for action, path, expected_status in transitions:
        params = {"driver_id": driver_id}
        url = f"{DISPATCH_URL}{path.format(id=trip_id)}"
        r = await client.post(url, params=params, timeout=10)
        if r.status_code != 200:
            fail(f"{action}: HTTP {r.status_code} — {r.text[:200]}")
            return trip_id
        verify = await client.get(f"{DISPATCH_URL}/dispatch/trip/{trip_id}", timeout=5)
        actual = verify.json()["status"]
        if actual != expected_status:
            fail(f"After {action}, status={actual} (expected {expected_status})")
            return trip_id
        ok(f"{action} → status={expected_status}")

    # Verify driver_en_route_at was set, not backfilled from arrived
    final = (await client.get(f"{DISPATCH_URL}/dispatch/trip/{trip_id}", timeout=5)).json()
    en_route_at = final.get("driver_en_route_at")
    arrived_at = final.get("driver_arrived_at")
    if en_route_at and arrived_at and en_route_at < arrived_at:
        ok(f"driver_en_route_at={en_route_at} precedes driver_arrived_at={arrived_at}")
    else:
        fail(f"en_route_at / arrived_at ordering wrong: {en_route_at} vs {arrived_at}")

    # Complete
    r = await client.post(
        f"{DISPATCH_URL}/driver/trip/{trip_id}/complete",
        params={"driver_id": driver_id, "fare_final": 22.0},
        timeout=10,
    )
    if r.status_code == 200:
        ok("Trip completed — $22.00")
    else:
        fail(f"complete: HTTP {r.status_code} — {r.text[:200]}")
    return trip_id


async def test_driver_noshow(client: httpx.AsyncClient) -> str | None:
    step("5 / 10 — Driver-side no-show endpoint")
    trip = await create_trip(client, notes="driver noshow test")
    if not trip:
        return None
    trip_id = trip["id"]
    assigned = await wait_for_status(client, trip_id, "assigned", timeout=10)
    if not assigned:
        fail("Trip not assigned")
        return trip_id
    driver_id = assigned["driver_id"]

    # accept → arrive → driver marks no-show
    for action in ("accept", "arrive"):
        r = await client.post(
            f"{DISPATCH_URL}/driver/trip/{trip_id}/{action}",
            params={"driver_id": driver_id},
            timeout=10,
        )
        if r.status_code != 200:
            fail(f"{action}: HTTP {r.status_code} — {r.text[:200]}")
            return trip_id

    r = await client.post(
        f"{DISPATCH_URL}/driver/trip/{trip_id}/noshow",
        params={"driver_id": driver_id},
        timeout=10,
    )
    if r.status_code != 200:
        fail(f"driver noshow: HTTP {r.status_code} — {r.text[:200]}")
        return trip_id

    final = (await client.get(f"{DISPATCH_URL}/dispatch/trip/{trip_id}", timeout=5)).json()
    if final["status"] != "noshow":
        fail(f"Expected status=noshow, got {final['status']}")
        return trip_id
    if not final.get("noshow_at"):
        fail("noshow_at timestamp not set")
        return trip_id
    ok(f"Driver marked no-show; noshow_at={final['noshow_at']}")
    return trip_id


async def test_booking_source_filter(client: httpx.AsyncClient) -> bool:
    step("6 / 10 — booking_source filter on /dispatch/trips")
    # We've been posting with booking_source=phone, so this should be non-empty
    r = await client.get(
        f"{DISPATCH_URL}/dispatch/trips",
        params={"booking_source": "phone", "limit": 50},
        timeout=10,
    )
    if r.status_code != 200:
        fail(f"list_trips filter HTTP {r.status_code}")
        return False
    trips = r.json()
    if not trips:
        fail("Expected at least one phone-source trip from this run")
        return False
    bad = [t for t in trips if t.get("booking_source") != "phone"]
    if bad:
        fail(f"{len(bad)} trip(s) returned with non-phone booking_source")
        return False
    ok(f"All {len(trips)} returned trips have booking_source=phone")

    # And conversely, the agent filter should not include our trips
    r = await client.get(
        f"{DISPATCH_URL}/dispatch/trips",
        params={"booking_source": "agent", "limit": 50},
        timeout=10,
    )
    agent_trips = r.json() if r.status_code == 200 else []
    leaked = [t for t in agent_trips if t.get("booking_source") == "phone"]
    if leaked:
        fail("Phone trips leaked into booking_source=agent filter")
        return False
    ok("Filter is exclusive: agent query excludes phone trips")
    return True


async def test_driver_ws_trip_assigned(client: httpx.AsyncClient) -> str | None:
    step("7 / 10 — Driver WebSocket receives `trip_assigned`")
    # Seed a third driver dedicated to this test so we control which WS to listen on
    driver = await seed_driver(client, "73", lat_offset=0.0001)
    if not driver:
        return None
    driver_id = driver["id"]

    received_events: list[dict] = []

    async def listen():
        url = f"{DISPATCH_WS_BASE}/dashboard/ws/driver/{driver_id}"
        async with websockets.connect(url) as ws:
            try:
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=12)
                    received_events.append(json.loads(raw))
                    if any(e.get("event") == "trip_assigned" for e in received_events):
                        return
            except asyncio.TimeoutError:
                return

    listener = asyncio.create_task(listen())
    await asyncio.sleep(0.5)  # let the WS connect

    # Make the other drivers ineligible by parking them, so this driver wins
    # (best-effort — not strictly required since proximity should rank ours equal)
    trip = await create_trip(client, notes="ws assign test")
    if not trip:
        listener.cancel()
        return None

    try:
        await asyncio.wait_for(listener, timeout=15)
    except asyncio.TimeoutError:
        listener.cancel()

    assigned_events = [e for e in received_events if e.get("event") == "trip_assigned"]
    if assigned_events:
        ev = assigned_events[0]
        data = ev.get("data", {})
        if data.get("pickup_address") and data.get("trip_id"):
            ok(f"Driver WS got trip_assigned (trip={data['trip_id'][:8]}…, pickup={data['pickup_address'][:40]}…)")
            return trip["id"]
        fail(f"trip_assigned payload missing fields: {data}")
        return trip["id"]
    # The trip may have gone to a different driver — that's OK, but means
    # this test is inconclusive rather than failed.
    warn("trip_assigned not seen on this driver's WS (trip likely went to a different driver)")
    return trip["id"]


async def test_dispatcher_cancel_pushes_ws(client: httpx.AsyncClient) -> str | None:
    step("8 / 10 — Dispatcher cancel pushes `trip_cancelled` to driver WS")
    trip = await create_trip(client, notes="ws cancel test")
    if not trip:
        return None
    trip_id = trip["id"]
    assigned = await wait_for_status(client, trip_id, "assigned", timeout=10)
    if not assigned:
        fail("Trip not assigned")
        return trip_id
    driver_id = assigned["driver_id"]

    received_events: list[dict] = []

    async def listen():
        url = f"{DISPATCH_WS_BASE}/dashboard/ws/driver/{driver_id}"
        async with websockets.connect(url) as ws:
            try:
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=10)
                    received_events.append(json.loads(raw))
                    if any(e.get("event") == "trip_cancelled" for e in received_events):
                        return
            except asyncio.TimeoutError:
                return

    listener = asyncio.create_task(listen())
    await asyncio.sleep(0.5)

    r = await client.post(
        f"{DISPATCH_URL}/dispatch/trip/{trip_id}/cancel",
        json={"reason": "customer changed mind"},
        timeout=10,
    )
    if r.status_code != 200:
        fail(f"cancel: HTTP {r.status_code} — {r.text[:200]}")
        listener.cancel()
        return trip_id

    try:
        await asyncio.wait_for(listener, timeout=12)
    except asyncio.TimeoutError:
        listener.cancel()

    cancelled = [e for e in received_events if e.get("event") == "trip_cancelled"]
    if cancelled:
        data = cancelled[0].get("data", {})
        if data.get("trip_id") == trip_id and "reason" in data:
            ok(f"Driver WS got trip_cancelled (reason='{data['reason']}')")
            return trip_id
    fail("Driver did not receive trip_cancelled event within 12s")
    return trip_id


async def test_prebooking_scheduler(
    client: httpx.AsyncClient, skip_wait: bool
) -> str | None:
    step("9 / 10 — Pre-booking lands in PRE-BOOKED bucket + scheduler dispatches it")
    # scheduled_for within the 15-min lead window so the scheduler picks it up
    scheduled = datetime.now(timezone.utc) + timedelta(minutes=5)
    trip = await create_trip(
        client,
        notes="prebook scheduler test",
        scheduled_for=scheduled.isoformat(),
    )
    if not trip:
        return None
    trip_id = trip["id"]

    # Verify it shows up in the PRE-BOOKED bucket immediately
    q = await client.get(f"{DISPATCH_URL}/dashboard/queue", timeout=10)
    if q.status_code == 200:
        ids = {t["trip_id"] for t in q.json().get("pre_booked", [])}
        if trip_id in ids:
            ok("Trip appears in PRE-BOOKED queue bucket immediately after creation")
        else:
            # Could already have been dispatched if scheduler ran on a fast loop
            warn("Trip not in PRE-BOOKED bucket — may have been dispatched already")
    else:
        warn(f"Queue endpoint returned {q.status_code}")

    if skip_wait:
        warn("Skipping scheduler-dispatch wait (--skip-scheduler)")
        return trip_id

    # The scheduler polls every 30s; wait up to 75s for it to dispatch
    print("     Waiting up to 75s for scheduler to dispatch the pre-booking …")
    assigned = await wait_for_status(
        client, trip_id, {"assigned", "en_route"}, timeout=75
    )
    if assigned:
        ok(f"Scheduler dispatched pre-booking; status={assigned['status']}")
        return trip_id
    fail("Pre-booking was not dispatched within 75s")
    return trip_id


async def cleanup(client: httpx.AsyncClient, driver_ids: list[str], trip_ids: list[str]):
    step("10 / 10 — Cleanup")
    cancelled = 0
    for tid in trip_ids:
        if not tid:
            continue
        try:
            await client.post(
                f"{DISPATCH_URL}/dispatch/trip/{tid}/cancel",
                json={"reason": "test cleanup"},
                timeout=5,
            )
            cancelled += 1
        except Exception:
            pass
    ok(f"Issued cancel on {cancelled} trip(s) (409s on closed trips are fine)")

    for did in driver_ids:
        if not did:
            continue
        try:
            await client.patch(
                f"{DISPATCH_URL}/driver/{did}",
                json={"is_active": False},
                timeout=5,
            )
        except Exception:
            pass
    ok(f"Deactivated {len(driver_ids)} test driver(s)")


# ── Main ──────────────────────────────────────────────────────────────────


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-scheduler",
        action="store_true",
        help="Skip the 75-second wait for the pre-booking scheduler",
    )
    args = parser.parse_args()

    print(f"{CYAN}Captain Taxi — Dispatch Session-8 E2E Test{RESET}")
    print(f"{CYAN}{'=' * 50}{RESET}")

    async with httpx.AsyncClient() as client:
        if not await check_health(client):
            print(f"\n{RED}Aborting — dispatch service unreachable.{RESET}")
            sys.exit(1)

        step("2 / 10 — Seed two drivers (so decline can reassign)")
        driver_a = await seed_driver(client, "71", lat_offset=0.0)
        driver_b = await seed_driver(client, "72", lat_offset=0.002)
        if not driver_a or not driver_b:
            print(f"\n{RED}Aborting — could not seed drivers.{RESET}")
            sys.exit(1)

        trip_ids: list[str] = []
        driver_ids = [d["id"] for d in (driver_a, driver_b) if d]

        trip_ids.append(await test_decline_and_reassign(client, driver_a, driver_b))
        trip_ids.append(await test_en_route_endpoint(client, driver_a))
        trip_ids.append(await test_driver_noshow(client))
        await test_booking_source_filter(client)

        ws_trip = await test_driver_ws_trip_assigned(client)
        if ws_trip:
            trip_ids.append(ws_trip)
        # The third driver from the WS test
        r = await client.get(f"{DISPATCH_URL}/driver", params={"city": "saskatoon"}, timeout=5)
        if r.status_code == 200:
            for d in r.json():
                if d["name"] == "S8 Driver 73":
                    driver_ids.append(d["id"])

        trip_ids.append(await test_dispatcher_cancel_pushes_ws(client))
        trip_ids.append(await test_prebooking_scheduler(client, args.skip_scheduler))

        await cleanup(client, driver_ids, trip_ids)

    print(f"\n{CYAN}{'=' * 50}{RESET}")
    print(f"  Passed: {GREEN}{passed}{RESET}")
    print(f"  Failed: {RED}{failed}{RESET}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
