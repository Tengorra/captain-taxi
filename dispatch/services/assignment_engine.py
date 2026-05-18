"""
AI-powered driver assignment engine.

Flow:
1. Collect available drivers near the pickup point (Redis geo query)
2. Enrich with DB data (rating, total_trips, status)
3. Score candidates with simple rules
4. If confidence is low or multiple candidates are close, ask Claude
5. Assign the winning driver, set a 90-second timeout in Redis
"""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from models.driver import Driver, DriverStatus
from models.trip import Trip, TripStatus
from redis_client import (
    find_nearby_drivers,
    set_driver_status,
    push_pending_assignment,
    acquire_assignment_lock,
    release_assignment_lock,
)
from services.notifications import notify_driver_trip_assigned
from services.websocket_manager import ws_manager

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Scoring helpers ────────────────────────────────────────────────────────


def _score_driver(candidate: dict, driver: Driver) -> float:
    """
    Deterministic score in [0, 1].  Higher is better.
    Weights: proximity 50%, rating 30%, trip load 20%.
    """
    max_km = settings.max_assignment_radius_km
    proximity_score = max(0.0, 1.0 - candidate["distance_km"] / max_km)

    # rating is 1–5; normalise to [0,1]
    rating_score = (driver.rating - 1.0) / 4.0

    # fewer total trips = fresher / less loaded driver (relative penalty)
    # We use an inverse-log to reward drivers who haven't done many trips today
    # (This is a simple heuristic; a real implementation would track daily counts)
    load_score = max(0.0, 1.0 - min(driver.total_trips, 100) / 100.0)

    return 0.5 * proximity_score + 0.3 * rating_score + 0.2 * load_score


# ── Claude consultation ────────────────────────────────────────────────────


async def _consult_claude(trip: Trip, candidates: list[dict]) -> tuple[str, str]:
    """
    Ask Claude to pick the best driver.
    Returns (driver_id, reasoning).
    """
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    candidates_text = json.dumps(
        [
            {
                "driver_id": c["driver_id"],
                "name": c["name"],
                "distance_km": c["distance_km"],
                "rating": c["rating"],
                "total_trips": c["total_trips"],
                "score": round(c["score"], 3),
            }
            for c in candidates
        ],
        indent=2,
    )

    prompt = f"""You are the dispatch AI for Captain Taxi, a taxi company in Saskatoon and Regina, Saskatchewan.

A new trip needs a driver assigned. Choose the BEST driver from the candidates below.

TRIP DETAILS:
- ID: {trip.id}
- City: {trip.city}
- Pickup: {trip.pickup_address}
- Dropoff: {trip.dropoff_address}
- Customer notes: {trip.notes or "none"}
- Scheduled for: {trip.scheduled_for or "ASAP"}

DRIVER CANDIDATES (sorted by preliminary score, highest first):
{candidates_text}

RULES:
1. Prefer the closest driver who has a rating >= 4.0
2. If two drivers are within 0.5 km of each other, prefer the higher-rated one
3. Never assign a driver whose score is below 0.2
4. Consider city match — only assign drivers confirmed in the same city

Return ONLY valid JSON in this exact format (no markdown, no explanation outside JSON):
{{
  "driver_id": "<the chosen driver_id>",
  "reasoning": "<one sentence explaining the choice>"
}}"""

    try:
        message = await client.messages.create(
            model=settings.claude_model,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        text = message.content[0].text.strip()
        result = json.loads(text)
        return result["driver_id"], result["reasoning"]
    except Exception as exc:
        logger.error("Claude assignment failed: %s", exc)
        # Fall back to the highest-scored candidate
        best = candidates[0]
        return best["driver_id"], f"Fallback: highest score ({best['score']:.2f}) after Claude error"


# ── Main assignment function ───────────────────────────────────────────────


async def assign_trip(trip: Trip, db: AsyncSession) -> Optional[Driver]:
    """
    Attempt to find and assign the best available driver for a trip.
    Returns the assigned Driver, or None if no suitable driver is found.
    """
    if not await acquire_assignment_lock(trip.id):
        logger.warning("Assignment lock already held for trip %s", trip.id)
        return None

    if trip.pickup_lat is None or trip.pickup_lng is None:
        logger.warning("Trip %s has no geocoords — cannot auto-assign", trip.id)
        return None

    # 1. Find nearby drivers in Redis
    nearby = await find_nearby_drivers(
        city=trip.city,
        lat=trip.pickup_lat,
        lng=trip.pickup_lng,
        radius_km=settings.max_assignment_radius_km,
        limit=settings.nearby_drivers_limit,
    )

    if not nearby:
        logger.info("No drivers found near trip %s in %s", trip.id, trip.city)
        return None

    driver_ids = [d["driver_id"] for d in nearby]

    # 2. Fetch driver records from DB (only online drivers)
    result = await db.execute(
        select(Driver).where(
            Driver.id.in_(driver_ids),
            Driver.status == DriverStatus.online,
            Driver.is_active == True,
            Driver.city == trip.city,
        )
    )
    db_drivers: dict[str, Driver] = {d.id: d for d in result.scalars().all()}

    if not db_drivers:
        logger.info("No online drivers available for trip %s", trip.id)
        return None

    # 3. Build enriched candidate list
    candidates = []
    for geo in nearby:
        driver = db_drivers.get(geo["driver_id"])
        if not driver:
            continue
        score = _score_driver(geo, driver)
        candidates.append(
            {
                **geo,
                "name": driver.name,
                "rating": driver.rating,
                "total_trips": driver.total_trips,
                "score": score,
            }
        )

    if not candidates:
        return None

    # Sort descending by score
    candidates.sort(key=lambda c: c["score"], reverse=True)

    # 4. Decide: use rules if clear winner, else consult Claude
    top = candidates[0]
    use_claude = (
        len(candidates) > 1
        and (candidates[0]["score"] - candidates[1]["score"]) < 0.1
    ) or top["score"] < 0.6

    if use_claude and settings.anthropic_api_key:
        chosen_id, reasoning = await _consult_claude(trip, candidates[:5])
    else:
        chosen_id = top["driver_id"]
        reasoning = f"Auto-selected: score={top['score']:.2f}, distance={top['distance_km']} km"

    chosen_driver = db_drivers.get(chosen_id)
    if not chosen_driver:
        logger.error("Claude chose unknown driver %s; falling back to top", chosen_id)
        chosen_driver = db_drivers[candidates[0]["driver_id"]]
        reasoning = "Fallback to top scorer after invalid Claude choice"

    # 5. Update trip record
    now = datetime.now(timezone.utc)
    trip.driver_id = chosen_driver.id
    trip.status = TripStatus.assigned
    trip.assigned_at = now
    trip.assignment_attempts += 1
    trip.ai_reasoning = reasoning
    await db.flush()

    # 6. Mark driver on_trip in Redis (optimistic — they still need to accept)
    await set_driver_status(chosen_driver.id, DriverStatus.on_trip.value)

    # 7. Queue the 90-second timeout
    deadline = time.time() + settings.assignment_timeout_seconds
    await push_pending_assignment(trip.id, chosen_driver.id, deadline)

    logger.info(
        "Trip %s assigned to driver %s (%s). Reasoning: %s",
        trip.id[:8],
        chosen_driver.name,
        chosen_driver.id[:8],
        reasoning,
    )

    # 8. Fire-and-forget notifications
    import asyncio
    asyncio.create_task(
        notify_driver_trip_assigned(
            driver_phone=chosen_driver.phone,
            driver_name=chosen_driver.name,
            trip_id=trip.id,
            pickup_address=trip.pickup_address,
            customer_name=trip.customer_name,
            customer_phone=trip.customer_phone,
        )
    )
    asyncio.create_task(
        ws_manager.notify_driver(
            chosen_driver.id,
            "trip_assigned",
            {
                "trip_id": trip.id,
                "pickup_address": trip.pickup_address,
                "dropoff_address": trip.dropoff_address,
                "customer_name": trip.customer_name,
                "customer_phone": trip.customer_phone,
                "notes": trip.notes,
                "fare_estimate": trip.fare_estimate,
            },
        )
    )
    asyncio.create_task(
        ws_manager.broadcast_dashboard(
            "trip_assigned",
            {
                "trip_id": trip.id,
                "driver_id": chosen_driver.id,
                "driver_name": chosen_driver.name,
                "reasoning": reasoning,
            },
        )
    )

    return chosen_driver


async def reassign_trip(trip: Trip, db: AsyncSession) -> Optional[Driver]:
    """Re-run assignment after a timeout, decline, or driver-cancel."""
    logger.info("Re-assigning trip %s (attempt %d)", trip.id[:8], trip.assignment_attempts + 1)
    trip.status = TripStatus.pending
    trip.driver_id = None
    trip.assigned_at = None
    await db.flush()
    # The previous assign_trip held a lock with a longer TTL than the
    # assignment timeout. Drop it so the next acquire succeeds.
    await release_assignment_lock(trip.id)
    return await assign_trip(trip, db)
