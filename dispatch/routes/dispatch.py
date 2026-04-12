"""
/dispatch — Booking intake + trip lifecycle management.
This is the primary inbound surface for ALL booking sources.
"""

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.trip import Trip, TripStatus
from models.driver import Driver, DriverStatus
from schemas.trip import TripCreate, TripResponse, TripUpdate, TripCancelRequest, TripReassignRequest
from services.assignment_engine import assign_trip, reassign_trip
from services.notifications import (
    notify_customer_driver_en_route,
    notify_customer_trip_cancelled,
)
from services.websocket_manager import ws_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dispatch", tags=["dispatch"])


async def _get_trip_or_404(trip_id: str, db: AsyncSession) -> Trip:
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = result.scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail=f"Trip {trip_id} not found")
    return trip


# ── Create trip ────────────────────────────────────────────────────────────


@router.post("/trip", response_model=TripResponse, status_code=201)
async def create_trip(
    payload: TripCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new trip. Immediately attempts auto-assignment unless scheduled_for
    is set in the future. Returns the trip object (status may be 'pending' or
    'assigned' depending on driver availability).
    """
    trip = Trip(**payload.model_dump())
    db.add(trip)
    await db.flush()  # get the ID before assignment

    now = datetime.now(timezone.utc)
    is_future = trip.scheduled_for and trip.scheduled_for > now

    if not is_future:
        # Attempt assignment in the background so the HTTP response is fast
        background_tasks.add_task(_attempt_assignment, trip.id)

    await db.commit()
    await db.refresh(trip)

    await ws_manager.broadcast_dashboard("trip_created", {"trip_id": trip.id, "city": trip.city})
    return trip


async def _attempt_assignment(trip_id: str):
    """Background task: assign a trip right after creation."""
    from database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Trip).where(Trip.id == trip_id))
        trip = result.scalar_one_or_none()
        if trip and trip.status == TripStatus.pending:
            await assign_trip(trip, db)
            await db.commit()


# ── Get / list trips ───────────────────────────────────────────────────────


@router.get("/trip/{trip_id}", response_model=TripResponse)
async def get_trip(trip_id: str, db: AsyncSession = Depends(get_db)):
    return await _get_trip_or_404(trip_id, db)


@router.get("/trips", response_model=list[TripResponse])
async def list_trips(
    status: TripStatus | None = None,
    city: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Trip).order_by(Trip.created_at.desc()).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(Trip.status == status)
    if city:
        stmt = stmt.where(Trip.city == city.lower())
    result = await db.execute(stmt)
    return result.scalars().all()


# ── Update trip ────────────────────────────────────────────────────────────


@router.patch("/trip/{trip_id}", response_model=TripResponse)
async def update_trip(
    trip_id: str,
    payload: TripUpdate,
    db: AsyncSession = Depends(get_db),
):
    trip = await _get_trip_or_404(trip_id, db)
    if trip.status in (TripStatus.completed, TripStatus.cancelled):
        raise HTTPException(status_code=409, detail="Cannot update a closed trip")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(trip, field, value)

    await db.commit()
    await db.refresh(trip)
    await ws_manager.broadcast_dashboard("trip_updated", {"trip_id": trip.id})
    return trip


# ── Cancel trip ────────────────────────────────────────────────────────────


@router.post("/trip/{trip_id}/cancel", response_model=TripResponse)
async def cancel_trip(
    trip_id: str,
    payload: TripCancelRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    trip = await _get_trip_or_404(trip_id, db)
    if trip.status in (TripStatus.completed, TripStatus.cancelled):
        raise HTTPException(status_code=409, detail="Trip already closed")

    # Free the driver if one was assigned
    if trip.driver_id:
        driver_result = await db.execute(select(Driver).where(Driver.id == trip.driver_id))
        driver = driver_result.scalar_one_or_none()
        if driver:
            driver.status = DriverStatus.online
            from redis_client import set_driver_status
            await set_driver_status(driver.id, DriverStatus.online.value)

    trip.status = TripStatus.cancelled
    trip.cancelled_at = datetime.now(timezone.utc)
    trip.cancellation_reason = payload.reason

    await db.commit()
    await db.refresh(trip)

    background_tasks.add_task(
        notify_customer_trip_cancelled,
        trip.customer_phone,
        trip.customer_name,
        payload.reason,
    )
    await ws_manager.broadcast_dashboard("trip_cancelled", {"trip_id": trip.id, "reason": payload.reason})
    return trip


# ── No-show ────────────────────────────────────────────────────────────────


@router.post("/trip/{trip_id}/noshow", response_model=TripResponse)
async def mark_noshow(
    trip_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Mark a trip as no-show (driver arrived, customer didn't appear)."""
    trip = await _get_trip_or_404(trip_id, db)
    if trip.status in (TripStatus.completed, TripStatus.cancelled, TripStatus.noshow):
        raise HTTPException(status_code=409, detail="Trip already closed")

    # Free the driver
    if trip.driver_id:
        driver_result = await db.execute(select(Driver).where(Driver.id == trip.driver_id))
        driver = driver_result.scalar_one_or_none()
        if driver:
            driver.status = DriverStatus.online
            from redis_client import set_driver_status
            await set_driver_status(driver.id, DriverStatus.online.value)

    trip.status = TripStatus.noshow
    trip.noshow_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(trip)
    await ws_manager.broadcast_dashboard("trip_noshow", {"trip_id": trip.id})
    return trip


# ── Manual reassign (dispatcher override) ─────────────────────────────────


@router.post("/trip/{trip_id}/reassign", response_model=TripResponse)
async def manual_reassign(
    trip_id: str,
    payload: TripReassignRequest,
    db: AsyncSession = Depends(get_db),
):
    trip = await _get_trip_or_404(trip_id, db)
    if trip.status in (TripStatus.completed, TripStatus.cancelled, TripStatus.in_progress):
        raise HTTPException(status_code=409, detail="Cannot reassign a trip in current status")

    driver_result = await db.execute(select(Driver).where(Driver.id == payload.driver_id))
    driver = driver_result.scalar_one_or_none()
    if not driver or not driver.is_active:
        raise HTTPException(status_code=404, detail="Driver not found or inactive")

    # Free old driver
    if trip.driver_id and trip.driver_id != payload.driver_id:
        old_result = await db.execute(select(Driver).where(Driver.id == trip.driver_id))
        old_driver = old_result.scalar_one_or_none()
        if old_driver:
            old_driver.status = DriverStatus.online
            from redis_client import set_driver_status
            await set_driver_status(old_driver.id, DriverStatus.online.value)

    trip.driver_id = driver.id
    trip.status = TripStatus.assigned
    trip.assigned_at = datetime.now(timezone.utc)
    trip.assignment_attempts += 1
    trip.ai_reasoning = f"Manual reassign by dispatcher. Reason: {payload.reason}"

    from redis_client import set_driver_status, push_pending_assignment
    import time
    from config import get_settings
    settings = get_settings()
    await set_driver_status(driver.id, DriverStatus.on_trip.value)
    deadline = time.time() + settings.assignment_timeout_seconds
    await push_pending_assignment(trip.id, driver.id, deadline)

    await db.commit()
    await db.refresh(trip)

    from services.notifications import notify_driver_trip_assigned
    asyncio.create_task(
        notify_driver_trip_assigned(
            driver_phone=driver.phone,
            driver_name=driver.name,
            trip_id=trip.id,
            pickup_address=trip.pickup_address,
            customer_name=trip.customer_name,
            customer_phone=trip.customer_phone,
        )
    )
    await ws_manager.broadcast_dashboard(
        "trip_reassigned",
        {"trip_id": trip.id, "driver_id": driver.id, "reason": payload.reason},
    )
    return trip
