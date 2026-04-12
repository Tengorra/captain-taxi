"""
/dashboard — Dispatcher dashboard API.
Provides live map data, stats, trip queue, and WebSocket streams.
"""

import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.driver import Driver, DriverStatus
from models.trip import Trip, TripStatus
from redis_client import get_driver_location, get_redis
from services.websocket_manager import ws_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# ── Live map ───────────────────────────────────────────────────────────────


@router.get("/map")
async def live_map(city: str | None = None, db: AsyncSession = Depends(get_db)):
    """
    Returns all active driver positions + active trips for the map overlay.
    Driver positions come from Redis (fastest); DB is the fallback.
    """
    driver_stmt = select(Driver).where(Driver.is_active == True, Driver.status != DriverStatus.offline)
    if city:
        driver_stmt = driver_stmt.where(Driver.city == city.lower())
    result = await db.execute(driver_stmt)
    drivers = result.scalars().all()

    driver_data = []
    for d in drivers:
        loc = await get_driver_location(d.id)
        lat = loc["lat"] if loc else d.last_lat
        lng = loc["lng"] if loc else d.last_lng
        driver_data.append(
            {
                "driver_id": d.id,
                "name": d.name,
                "status": d.status.value,
                "city": d.city,
                "vehicle_plate": d.vehicle_plate,
                "vehicle_model": d.vehicle_model,
                "rating": d.rating,
                "lat": lat,
                "lng": lng,
            }
        )

    trip_stmt = select(Trip).where(
        Trip.status.in_([TripStatus.pending, TripStatus.assigned, TripStatus.en_route, TripStatus.arrived, TripStatus.in_progress])
    )
    if city:
        trip_stmt = trip_stmt.where(Trip.city == city.lower())
    trip_result = await db.execute(trip_stmt)
    trips = trip_result.scalars().all()

    trip_data = [
        {
            "trip_id": t.id,
            "status": t.status.value,
            "city": t.city,
            "pickup_address": t.pickup_address,
            "pickup_lat": t.pickup_lat,
            "pickup_lng": t.pickup_lng,
            "dropoff_address": t.dropoff_address,
            "dropoff_lat": t.dropoff_lat,
            "dropoff_lng": t.dropoff_lng,
            "driver_id": t.driver_id,
            "customer_name": t.customer_name,
            "requested_at": t.requested_at.isoformat() if t.requested_at else None,
        }
        for t in trips
    ]

    return {"drivers": driver_data, "trips": trip_data}


# ── Trip queue ─────────────────────────────────────────────────────────────


@router.get("/queue")
async def trip_queue(
    city: str | None = None,
    history_hours: int = 4,
    db: AsyncSession = Depends(get_db),
):
    """
    Active trips grouped by status tab, matching the iCabbi job board.
    Active statuses: DISPATCH (pending), PRE-BOOKED (scheduled), BOOKED (assigned/en_route/arrived),
    IN-PROGRESS (in_progress), COMPLETED, CANCELLED, NOSHOW.
    history_hours controls how far back completed/cancelled/noshow are returned.
    """
    from datetime import timedelta
    since = datetime.now(timezone.utc) - timedelta(hours=history_hours)

    # Active trips (no time filter)
    active_stmt = select(Trip).where(
        Trip.status.in_([TripStatus.pending, TripStatus.assigned, TripStatus.en_route,
                         TripStatus.arrived, TripStatus.in_progress])
    ).order_by(Trip.requested_at.asc())
    if city:
        active_stmt = active_stmt.where(Trip.city == city.lower())

    # Historical (completed, cancelled, noshow) within window
    hist_stmt = select(Trip).where(
        Trip.status.in_([TripStatus.completed, TripStatus.cancelled, TripStatus.noshow]),
        Trip.created_at >= since,
    ).order_by(Trip.requested_at.desc()).limit(100)
    if city:
        hist_stmt = hist_stmt.where(Trip.city == city.lower())

    active_result = await db.execute(active_stmt)
    hist_result = await db.execute(hist_stmt)
    all_trips = list(active_result.scalars().all()) + list(hist_result.scalars().all())

    def _serialize(t: Trip) -> dict:
        return {
            "trip_id": t.id,
            "customer_name": t.customer_name,
            "customer_phone": t.customer_phone,
            "customer_email": t.customer_email,
            "pickup_address": t.pickup_address,
            "dropoff_address": t.dropoff_address,
            "via_address": t.via_address,
            "city": t.city,
            "driver_id": t.driver_id,
            "priority": t.priority,
            "instructions": t.instructions,
            "site": t.site,
            "requested_at": t.requested_at.isoformat() if t.requested_at else None,
            "scheduled_for": t.scheduled_for.isoformat() if t.scheduled_for else None,
            "assigned_at": t.assigned_at.isoformat() if t.assigned_at else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            "cancelled_at": t.cancelled_at.isoformat() if t.cancelled_at else None,
            "noshow_at": t.noshow_at.isoformat() if t.noshow_at else None,
            "fare_estimate": t.fare_estimate,
            "fare_final": t.fare_final,
            "notes": t.notes,
            "booking_source": t.booking_source.value,
            "status": t.status.value,
        }

    queue: dict[str, list] = {
        "dispatch": [],    # pending (not pre-booked)
        "pre_booked": [],  # scheduled for a future time
        "booked": [],      # assigned / en_route / arrived
        "in_progress": [], # in_progress
        "completed": [],
        "cancelled": [],
        "noshow": [],
    }
    for t in all_trips:
        if t.status == TripStatus.pending:
            if t.scheduled_for and t.scheduled_for > datetime.now(timezone.utc):
                queue["pre_booked"].append(_serialize(t))
            else:
                queue["dispatch"].append(_serialize(t))
        elif t.status in (TripStatus.assigned, TripStatus.en_route, TripStatus.arrived):
            queue["booked"].append(_serialize(t))
        elif t.status == TripStatus.in_progress:
            queue["in_progress"].append(_serialize(t))
        elif t.status == TripStatus.completed:
            queue["completed"].append(_serialize(t))
        elif t.status == TripStatus.cancelled:
            queue["cancelled"].append(_serialize(t))
        elif t.status == TripStatus.noshow:
            queue["noshow"].append(_serialize(t))

    return queue


# ── Stats ──────────────────────────────────────────────────────────────────


@router.get("/stats")
async def stats(city: str | None = None, db: AsyncSession = Depends(get_db)):
    """Aggregated stats for the last 24 hours."""
    since = datetime.now(timezone.utc) - timedelta(hours=24)

    base = select(Trip).where(Trip.created_at >= since)
    if city:
        base = base.where(Trip.city == city.lower())

    # Trips completed in window
    completed_result = await db.execute(
        base.where(Trip.status == TripStatus.completed)
    )
    completed_trips = completed_result.scalars().all()

    # Average wait time (requested_at → assigned_at)
    wait_times = [
        (t.assigned_at - t.requested_at).total_seconds()
        for t in completed_trips
        if t.assigned_at and t.requested_at
    ]
    avg_wait = round(sum(wait_times) / len(wait_times) / 60, 1) if wait_times else None

    # Trips per hour
    trips_per_hour = round(len(completed_trips) / 24, 1)

    # By city
    by_city_result = await db.execute(
        select(Trip.city, func.count(Trip.id))
        .where(Trip.created_at >= since)
        .group_by(Trip.city)
    )
    by_city = {row[0]: row[1] for row in by_city_result.all()}

    # Active drivers
    online_result = await db.execute(
        select(func.count(Driver.id)).where(
            Driver.status != DriverStatus.offline,
            Driver.is_active == True,
            *([Driver.city == city.lower()] if city else []),
        )
    )
    online_drivers = online_result.scalar()

    # Pending trips waiting for driver
    pending_result = await db.execute(
        select(func.count(Trip.id)).where(
            Trip.status == TripStatus.pending,
            Trip.created_at >= since,
            *([Trip.city == city.lower()] if city else []),
        )
    )
    pending_count = pending_result.scalar()

    return {
        "window_hours": 24,
        "completed_trips": len(completed_trips),
        "trips_per_hour": trips_per_hour,
        "avg_wait_minutes": avg_wait,
        "active_drivers": online_drivers,
        "pending_trips": pending_count,
        "by_city": by_city,
    }


# ── WebSocket — dispatcher dashboard ──────────────────────────────────────


@router.websocket("/ws")
async def dashboard_ws(websocket: WebSocket):
    """
    Connect to receive real-time events:
      - driver_location        { driver_id, lat, lng, city }
      - driver_status_changed  { driver_id, status }
      - trip_created           { trip_id, city }
      - trip_assigned          { trip_id, driver_id, reasoning }
      - trip_updated           { trip_id }
      - trip_cancelled         { trip_id, reason }
      - trip_reassigned        { trip_id, driver_id, reason }
      - trip_accepted          { trip_id, driver_id }
      - driver_arrived         { trip_id }
      - trip_in_progress       { trip_id }
      - trip_completed         { trip_id, fare }
    """
    await ws_manager.connect(websocket, "dashboard")
    try:
        while True:
            # Keep-alive: read pings but ignore content
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "dashboard")


# ── WebSocket — individual driver ──────────────────────────────────────────


@router.websocket("/ws/driver/{driver_id}")
async def driver_ws(driver_id: str, websocket: WebSocket):
    """
    Per-driver WebSocket. Events pushed to the driver:
      - trip_assigned  { trip_id, pickup_address, ... }
      - trip_status    { trip_id, status }
    """
    await ws_manager.connect(websocket, f"driver:{driver_id}")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, f"driver:{driver_id}")
