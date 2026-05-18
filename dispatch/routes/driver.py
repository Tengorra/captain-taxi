"""
/driver — Mobile API + driver management endpoints.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.driver import Driver, DriverStatus
from models.trip import Trip, TripStatus
from models.location import LocationHistory
from schemas.driver import (
    DriverCreate,
    DriverUpdate,
    DriverResponse,
    DriverStatusUpdate,
    DriverLocationUpdate,
)
from schemas.trip import TripResponse
from redis_client import set_driver_location, set_driver_status
from services.websocket_manager import ws_manager
from services.notifications import notify_customer_driver_en_route

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/driver", tags=["driver"])


async def _get_driver_or_404(driver_id: str, db: AsyncSession) -> Driver:
    result = await db.execute(select(Driver).where(Driver.id == driver_id))
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    return driver


# ── CRUD ───────────────────────────────────────────────────────────────────


@router.post("", response_model=DriverResponse, status_code=201)
async def create_driver(payload: DriverCreate, db: AsyncSession = Depends(get_db)):
    driver = Driver(**payload.model_dump(exclude_none=True))
    db.add(driver)
    await db.commit()
    await db.refresh(driver)
    return driver


@router.get("/{driver_id}", response_model=DriverResponse)
async def get_driver(driver_id: str, db: AsyncSession = Depends(get_db)):
    return await _get_driver_or_404(driver_id, db)


@router.get("", response_model=list[DriverResponse])
async def list_drivers(
    city: str | None = None,
    status: DriverStatus | None = None,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Driver).order_by(Driver.name)
    if city:
        stmt = stmt.where(Driver.city == city.lower())
    if status:
        stmt = stmt.where(Driver.status == status)
    if active_only:
        stmt = stmt.where(Driver.is_active == True)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.patch("/{driver_id}", response_model=DriverResponse)
async def update_driver(
    driver_id: str,
    payload: DriverUpdate,
    db: AsyncSession = Depends(get_db),
):
    driver = await _get_driver_or_404(driver_id, db)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(driver, field, value)
    await db.commit()
    await db.refresh(driver)
    return driver


# ── Mobile API ─────────────────────────────────────────────────────────────


@router.get("/me/trips", response_model=list[TripResponse])
async def get_my_trips(
    driver_id: str,  # In a real system this comes from JWT auth
    db: AsyncSession = Depends(get_db),
):
    """Upcoming/active trips for a driver."""
    result = await db.execute(
        select(Trip)
        .where(
            Trip.driver_id == driver_id,
            Trip.status.in_([TripStatus.assigned, TripStatus.en_route, TripStatus.arrived, TripStatus.in_progress]),
        )
        .order_by(Trip.scheduled_for.asc().nullsfirst(), Trip.created_at.asc())
    )
    return result.scalars().all()


@router.post("/me/status", response_model=DriverResponse)
async def update_my_status(
    driver_id: str,  # from JWT in real impl
    payload: DriverStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    driver = await _get_driver_or_404(driver_id, db)
    driver.status = payload.status
    await set_driver_status(driver.id, payload.status.value)
    await db.commit()
    await db.refresh(driver)
    await ws_manager.broadcast_dashboard(
        "driver_status_changed",
        {"driver_id": driver.id, "status": payload.status.value},
    )
    return driver


@router.post("/me/location")
async def update_my_location(
    driver_id: str,  # from JWT in real impl
    payload: DriverLocationUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Push a GPS coordinate from the driver's mobile app."""
    driver = await _get_driver_or_404(driver_id, db)

    # Update Redis (fast path — dashboards read this)
    await set_driver_location(driver.id, payload.lat, payload.lng, driver.city)

    # Update DB columns
    driver.last_lat = payload.lat
    driver.last_lng = payload.lng
    driver.last_location_at = datetime.now(timezone.utc)

    # Store in location history
    history = LocationHistory(
        driver_id=driver.id,
        trip_id=payload.trip_id,
        lat=payload.lat,
        lng=payload.lng,
        speed_kmh=payload.speed_kmh,
        heading=payload.heading,
    )
    db.add(history)
    await db.commit()

    # Push to dashboard WebSocket
    await ws_manager.broadcast_dashboard(
        "driver_location",
        {
            "driver_id": driver.id,
            "lat": payload.lat,
            "lng": payload.lng,
            "city": driver.city,
        },
    )
    return {"ok": True}


# ── Trip action endpoints ──────────────────────────────────────────────────


@router.post("/trip/{trip_id}/accept")
async def accept_trip(
    trip_id: str,
    driver_id: str,  # from JWT in real impl
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = result.scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    if trip.driver_id != driver_id:
        raise HTTPException(status_code=403, detail="This trip is not assigned to you")
    if trip.status != TripStatus.assigned:
        raise HTTPException(status_code=409, detail=f"Trip is in status {trip.status}, cannot accept")

    # Confirmed — remove from timeout queue
    from redis_client import get_redis
    import json, time
    r = await get_redis()
    # Clean up any pending assignment entry for this trip
    items = await r.zrangebyscore("pending_assignments", "-inf", "+inf")
    for item in items:
        data = json.loads(item)
        if data.get("trip_id") == trip_id:
            await r.zrem("pending_assignments", item)
            break

    await ws_manager.broadcast_dashboard("trip_accepted", {"trip_id": trip.id, "driver_id": driver_id})
    return {"ok": True, "trip_id": trip.id}


@router.post("/trip/{trip_id}/arrive")
async def driver_arrived(
    trip_id: str,
    driver_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = result.scalar_one_or_none()
    if not trip or trip.driver_id != driver_id:
        raise HTTPException(status_code=404, detail="Trip not found or not assigned to you")
    if trip.status not in (TripStatus.assigned, TripStatus.en_route):
        raise HTTPException(status_code=409, detail="Unexpected trip status")

    trip.status = TripStatus.arrived
    trip.driver_arrived_at = datetime.now(timezone.utc)
    await db.commit()

    await ws_manager.broadcast_dashboard("driver_arrived", {"trip_id": trip.id})
    await ws_manager.notify_driver(driver_id, "trip_status", {"trip_id": trip.id, "status": "arrived"})
    return {"ok": True}


@router.post("/trip/{trip_id}/pickup")
async def start_trip(
    trip_id: str,
    driver_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = result.scalar_one_or_none()
    if not trip or trip.driver_id != driver_id:
        raise HTTPException(status_code=404, detail="Trip not found or not assigned to you")
    if trip.status != TripStatus.arrived:
        raise HTTPException(status_code=409, detail="Driver has not arrived yet")

    trip.status = TripStatus.in_progress
    trip.pickup_at = datetime.now(timezone.utc)
    if not trip.driver_en_route_at:
        trip.driver_en_route_at = trip.driver_arrived_at

    await db.commit()

    # Notify customer
    driver_result = await db.execute(select(Driver).where(Driver.id == driver_id))
    driver = driver_result.scalar_one_or_none()
    if driver:
        import asyncio
        asyncio.create_task(
            notify_customer_driver_en_route(
                customer_phone=trip.customer_phone,
                customer_name=trip.customer_name,
                driver_name=driver.name,
                vehicle_model=driver.vehicle_model,
                vehicle_plate=driver.vehicle_plate,
            )
        )

    await ws_manager.broadcast_dashboard("trip_in_progress", {"trip_id": trip.id})
    return {"ok": True}


@router.post("/trip/{trip_id}/complete")
async def complete_trip(
    trip_id: str,
    driver_id: str,
    fare_final: float | None = None,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = result.scalar_one_or_none()
    if not trip or trip.driver_id != driver_id:
        raise HTTPException(status_code=404, detail="Trip not found or not assigned to you")
    if trip.status != TripStatus.in_progress:
        raise HTTPException(status_code=409, detail="Trip is not in progress")

    trip.status = TripStatus.completed
    trip.completed_at = datetime.now(timezone.utc)
    if fare_final is not None:
        trip.fare_final = fare_final

    # Update driver stats
    driver_result = await db.execute(select(Driver).where(Driver.id == driver_id))
    driver = driver_result.scalar_one_or_none()
    if driver:
        driver.status = DriverStatus.online
        driver.total_trips += 1
        await set_driver_status(driver.id, DriverStatus.online.value)

    await db.commit()

    await ws_manager.broadcast_dashboard("trip_completed", {"trip_id": trip.id, "fare": fare_final})
    return {"ok": True}


@router.post("/trip/{trip_id}/cancel")
async def driver_cancel_trip(
    trip_id: str,
    driver_id: str,
    reason: str = "",
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = result.scalar_one_or_none()
    if not trip or trip.driver_id != driver_id:
        raise HTTPException(status_code=404, detail="Trip not found or not assigned to you")
    if trip.status in (TripStatus.completed, TripStatus.cancelled):
        raise HTTPException(status_code=409, detail="Trip already closed")

    trip.status = TripStatus.pending
    trip.driver_id = None
    trip.assigned_at = None
    trip.cancellation_reason = f"Driver cancelled: {reason}"

    driver_result = await db.execute(select(Driver).where(Driver.id == driver_id))
    driver = driver_result.scalar_one_or_none()
    if driver:
        driver.status = DriverStatus.online
        await set_driver_status(driver.id, DriverStatus.online.value)

    await db.commit()

    # Re-attempt assignment
    import asyncio
    from routes.dispatch import _attempt_assignment
    asyncio.create_task(_attempt_assignment(trip.id))

    await ws_manager.broadcast_dashboard("driver_cancelled_trip", {"trip_id": trip.id})
    return {"ok": True}


@router.post("/trip/{trip_id}/decline")
async def decline_trip(
    trip_id: str,
    driver_id: str,
    reason: str = "",
    db: AsyncSession = Depends(get_db),
):
    """
    Driver explicitly declines an assigned trip before accepting it.
    Frees the driver, removes the pending-assignment timeout entry,
    and immediately re-runs assignment (excluding this driver via
    DriverStatus rules — they are now `online` but reassignment will
    pick the next-best candidate).
    """
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = result.scalar_one_or_none()
    if not trip or trip.driver_id != driver_id:
        raise HTTPException(status_code=404, detail="Trip not found or not assigned to you")
    if trip.status != TripStatus.assigned:
        raise HTTPException(status_code=409, detail=f"Cannot decline a trip in status {trip.status}")

    # Pull this trip out of the timeout queue
    from redis_client import get_redis
    import json
    r = await get_redis()
    items = await r.zrangebyscore("pending_assignments", "-inf", "+inf")
    for item in items:
        data = json.loads(item)
        if data.get("trip_id") == trip_id:
            await r.zrem("pending_assignments", item)
            break

    driver_result = await db.execute(select(Driver).where(Driver.id == driver_id))
    driver = driver_result.scalar_one_or_none()
    if driver:
        driver.status = DriverStatus.online
        await set_driver_status(driver.id, DriverStatus.online.value)

    trip.ai_reasoning = f"Declined by {driver.name if driver else driver_id}: {reason or 'no reason given'}"
    await db.commit()

    await ws_manager.broadcast_dashboard(
        "trip_declined",
        {"trip_id": trip.id, "driver_id": driver_id, "reason": reason},
    )

    # Re-attempt assignment in the background
    import asyncio
    from services.assignment_engine import reassign_trip
    async def _do_reassign():
        from database import AsyncSessionLocal
        async with AsyncSessionLocal() as s:
            r2 = await s.execute(select(Trip).where(Trip.id == trip_id))
            t2 = r2.scalar_one_or_none()
            if t2:
                await reassign_trip(t2, s)
                await s.commit()
    asyncio.create_task(_do_reassign())

    return {"ok": True}


@router.post("/trip/{trip_id}/en_route")
async def driver_en_route(
    trip_id: str,
    driver_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Driver has accepted and is now heading to the pickup point."""
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = result.scalar_one_or_none()
    if not trip or trip.driver_id != driver_id:
        raise HTTPException(status_code=404, detail="Trip not found or not assigned to you")
    if trip.status != TripStatus.assigned:
        raise HTTPException(status_code=409, detail=f"Cannot start en-route from status {trip.status}")

    trip.status = TripStatus.en_route
    trip.driver_en_route_at = datetime.now(timezone.utc)
    await db.commit()

    await ws_manager.broadcast_dashboard("driver_en_route", {"trip_id": trip.id, "driver_id": driver_id})
    return {"ok": True}


@router.post("/trip/{trip_id}/noshow")
async def driver_mark_noshow(
    trip_id: str,
    driver_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Driver arrived at pickup but customer did not appear."""
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = result.scalar_one_or_none()
    if not trip or trip.driver_id != driver_id:
        raise HTTPException(status_code=404, detail="Trip not found or not assigned to you")
    if trip.status not in (TripStatus.arrived, TripStatus.assigned, TripStatus.en_route):
        raise HTTPException(status_code=409, detail=f"Cannot mark no-show from status {trip.status}")

    trip.status = TripStatus.noshow
    trip.noshow_at = datetime.now(timezone.utc)

    driver_result = await db.execute(select(Driver).where(Driver.id == driver_id))
    driver = driver_result.scalar_one_or_none()
    if driver:
        driver.status = DriverStatus.online
        await set_driver_status(driver.id, DriverStatus.online.value)

    await db.commit()
    await ws_manager.broadcast_dashboard("trip_noshow", {"trip_id": trip.id, "driver_id": driver_id})
    return {"ok": True}
