"""
Pre-booking dispatcher.

A pre-booked trip is one created with a future `scheduled_for` timestamp.
On creation, auto-assignment is skipped and the trip lives in the
PRE-BOOKED bucket of the queue.

This worker wakes periodically, finds pre-bookings whose pickup time is
within `PREBOOK_DISPATCH_LEAD_MINUTES` minutes, and runs the standard
assignment engine on each.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select

from database import AsyncSessionLocal
from models.trip import Trip, TripStatus
from services.assignment_engine import assign_trip

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 30
PREBOOK_DISPATCH_LEAD_MINUTES = 15


async def run_prebook_scheduler():
    """Infinite loop — dispatch pre-bookings as their pickup time approaches."""
    logger.info(
        "Pre-booking scheduler started (poll=%ds, lead=%dmin)",
        POLL_INTERVAL_SECONDS,
        PREBOOK_DISPATCH_LEAD_MINUTES,
    )
    while True:
        try:
            await _process_due_prebookings()
        except Exception as exc:
            logger.exception("Pre-booking scheduler error: %s", exc)
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def _process_due_prebookings():
    cutoff = datetime.now(timezone.utc) + timedelta(minutes=PREBOOK_DISPATCH_LEAD_MINUTES)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Trip).where(
                Trip.status == TripStatus.pending,
                Trip.driver_id.is_(None),
                Trip.scheduled_for.isnot(None),
                Trip.scheduled_for <= cutoff,
            )
        )
        due = result.scalars().all()
        if not due:
            return
        logger.info("Pre-booking scheduler: dispatching %d due trip(s)", len(due))
        for trip in due:
            try:
                await assign_trip(trip, db)
            except Exception:
                logger.exception("Failed to dispatch pre-booking %s", trip.id)
        await db.commit()
