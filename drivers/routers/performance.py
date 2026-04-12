"""Performance tracking endpoints."""
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.driver import Driver
from models.performance import DriverMetrics, PerformanceFlag, Complaint
from agents.performance_agent import (
    record_weekly_metrics, send_weekly_report, add_complaint
)

router = APIRouter(prefix="/drivers", tags=["performance"])


class MetricsInput(BaseModel):
    week_start: date
    trips_completed: int
    trips_cancelled: int
    trips_offered: int
    avg_rating: Optional[float] = None
    late_arrivals: int = 0
    income_earned: float = 0.0
    hours_online: float = 0.0


class ComplaintInput(BaseModel):
    source: str  # "customer", "internal", "dispatch"
    description: str
    severity: int = 1
    trip_id: Optional[str] = None


@router.post("/{driver_id}/metrics")
async def submit_metrics(
    driver_id: int,
    payload: MetricsInput,
    db: AsyncSession = Depends(get_db),
):
    """Ingest weekly metrics for a driver (from dispatch system or manual entry)."""
    result = await db.execute(select(Driver).where(Driver.id == driver_id))
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(404, "Driver not found")

    metrics = await record_weekly_metrics(
        driver=driver,
        week_start=payload.week_start,
        trips_completed=payload.trips_completed,
        trips_cancelled=payload.trips_cancelled,
        trips_offered=payload.trips_offered,
        avg_rating=payload.avg_rating,
        late_arrivals=payload.late_arrivals,
        income_earned=payload.income_earned,
        hours_online=payload.hours_online,
        db=db,
    )
    return {
        "driver_id": driver_id,
        "week_start": str(metrics.week_start),
        "cancellation_rate": f"{(metrics.cancellation_rate or 0):.1%}",
        "avg_rating": metrics.avg_rating,
        "income_earned": metrics.income_earned,
    }


@router.get("/{driver_id}/metrics")
async def get_metrics(
    driver_id: int,
    week_start: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get performance metrics for a driver."""
    query = select(DriverMetrics).where(DriverMetrics.driver_id == driver_id)
    if week_start:
        query = query.where(DriverMetrics.week_start == week_start)
    result = await db.execute(query.order_by(DriverMetrics.week_start.desc()).limit(12))
    rows = result.scalars().all()
    return [
        {
            "week_start": str(m.week_start),
            "trips_completed": m.trips_completed,
            "trips_cancelled": m.trips_cancelled,
            "cancellation_rate": f"{(m.cancellation_rate or 0):.1%}",
            "avg_rating": m.avg_rating,
            "late_arrivals": m.late_arrivals,
            "income_earned": m.income_earned,
            "hours_online": m.hours_online,
        }
        for m in rows
    ]


@router.post("/{driver_id}/metrics/send-report")
async def send_performance_report(
    driver_id: int,
    week_start: date,
    db: AsyncSession = Depends(get_db),
):
    """Send the weekly performance report to a driver."""
    result = await db.execute(select(Driver).where(Driver.id == driver_id))
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(404, "Driver not found")

    sent = await send_weekly_report(driver, week_start, db)
    if not sent:
        raise HTTPException(404, f"No metrics found for driver {driver_id} for week {week_start}")
    return {"success": True}


@router.get("/{driver_id}/flags")
async def get_flags(driver_id: int, db: AsyncSession = Depends(get_db)):
    """Get all performance flags for a driver."""
    result = await db.execute(
        select(PerformanceFlag)
        .where(PerformanceFlag.driver_id == driver_id)
        .order_by(PerformanceFlag.created_at.desc())
    )
    flags = result.scalars().all()
    return [
        {
            "id": f.id,
            "flag_type": f.flag_type.value,
            "status": f.status.value,
            "detail": f.detail,
            "value": f.value,
            "week_start": str(f.week_start) if f.week_start else None,
            "created_at": f.created_at,
        }
        for f in flags
    ]


@router.post("/{driver_id}/complaints")
async def submit_complaint(
    driver_id: int,
    payload: ComplaintInput,
    db: AsyncSession = Depends(get_db),
):
    """Log a complaint against a driver."""
    result = await db.execute(select(Driver).where(Driver.id == driver_id))
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(404, "Driver not found")

    complaint = await add_complaint(
        driver=driver,
        source=payload.source,
        description=payload.description,
        severity=payload.severity,
        trip_id=payload.trip_id,
        db=db,
    )
    return {"complaint_id": complaint.id, "driver_id": driver_id}


@router.get("/{driver_id}/complaints")
async def get_complaints(driver_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Complaint)
        .where(Complaint.driver_id == driver_id)
        .order_by(Complaint.created_at.desc())
    )
    complaints = result.scalars().all()
    return [
        {
            "id": c.id,
            "source": c.source,
            "description": c.description,
            "severity": c.severity,
            "trip_id": c.trip_id,
            "resolved": c.resolved,
            "created_at": c.created_at,
        }
        for c in complaints
    ]
