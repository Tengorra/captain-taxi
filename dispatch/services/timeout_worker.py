"""
Background worker: polls Redis for pending assignments that have expired
(driver didn't accept within 90 seconds) and re-assigns the trip.

Runs as an asyncio task started from main.py lifespan.
"""

import asyncio
import logging
import time

from sqlalchemy import select

from database import AsyncSessionLocal
from models.trip import Trip, TripStatus
from models.driver import Driver, DriverStatus
from redis_client import pop_expired_assignments, set_driver_status
from services.assignment_engine import reassign_trip
from services.websocket_manager import ws_manager

logger = logging.getLogger(__name__)

MAX_ASSIGNMENT_ATTEMPTS = 3
POLL_INTERVAL_SECONDS = 5


async def run_timeout_worker():
    """
    Infinite loop — wakes every POLL_INTERVAL_SECONDS seconds to handle expired assignments.
    Designed to be launched with asyncio.create_task() during app startup.
    """
    logger.info("Timeout worker started (poll interval=%ds)", POLL_INTERVAL_SECONDS)
    while True:
        try:
            await _process_expired()
        except Exception as exc:
            logger.exception("Timeout worker error: %s", exc)
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def _process_expired():
    now = time.time()
    expired = await pop_expired_assignments(now)
    if not expired:
        return

    async with AsyncSessionLocal() as db:
        for item in expired:
            trip_id = item["trip_id"]
            timed_out_driver_id = item["driver_id"]

            result = await db.execute(select(Trip).where(Trip.id == trip_id))
            trip = result.scalar_one_or_none()

            if not trip:
                logger.warning("Expired assignment for unknown trip %s", trip_id)
                continue

            if trip.status != TripStatus.assigned:
                # Driver already accepted, trip progressed, or cancelled — skip
                continue

            logger.info(
                "Trip %s timed out waiting for driver %s (attempt %d)",
                trip_id[:8],
                timed_out_driver_id[:8],
                trip.assignment_attempts,
            )

            # Free the timed-out driver
            driver_result = await db.execute(
                select(Driver).where(Driver.id == timed_out_driver_id)
            )
            timed_out_driver = driver_result.scalar_one_or_none()
            if timed_out_driver:
                timed_out_driver.status = DriverStatus.online
                await set_driver_status(timed_out_driver_id, DriverStatus.online.value)

            await ws_manager.broadcast_dashboard(
                "assignment_timeout",
                {"trip_id": trip_id, "driver_id": timed_out_driver_id},
            )

            if trip.assignment_attempts >= MAX_ASSIGNMENT_ATTEMPTS:
                logger.warning(
                    "Trip %s exhausted %d assignment attempts — leaving pending for dispatcher",
                    trip_id[:8],
                    MAX_ASSIGNMENT_ATTEMPTS,
                )
                trip.status = TripStatus.pending
                trip.driver_id = None
                trip.assigned_at = None
                trip.ai_reasoning += " | Exhausted auto-assignment attempts"
                await db.commit()
                await ws_manager.broadcast_dashboard(
                    "trip_needs_manual_assign",
                    {"trip_id": trip_id, "attempts": trip.assignment_attempts},
                )
                continue

            # Try to find a new driver
            new_driver = await reassign_trip(trip, db)
            await db.commit()

            if not new_driver:
                logger.info("No driver available for re-assignment of trip %s", trip_id[:8])
                await ws_manager.broadcast_dashboard(
                    "trip_needs_manual_assign",
                    {"trip_id": trip_id, "attempts": trip.assignment_attempts},
                )
