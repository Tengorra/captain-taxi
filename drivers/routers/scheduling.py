"""Scheduling endpoints — availability submission, schedule build, shift management."""
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.driver import Driver
from models.schedule import DriverAvailability, Shift, ShiftAssignment, TimeBlock
from agents.scheduling_agent import (
    submit_availability, build_weekly_schedule, send_weekly_schedule
)

router = APIRouter(prefix="/drivers", tags=["scheduling"])


class AvailabilitySlot(BaseModel):
    day_of_week: int  # 0=Monday … 6=Sunday
    time_block: TimeBlock
    is_available: bool = True


class AvailabilityRequest(BaseModel):
    week_start: date
    slots: list[AvailabilitySlot]


@router.post("/{driver_id}/availability")
async def submit_driver_availability(
    driver_id: int,
    payload: AvailabilityRequest,
    db: AsyncSession = Depends(get_db),
):
    """Driver submits their availability for a given week."""
    result = await db.execute(select(Driver).where(Driver.id == driver_id))
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(404, "Driver not found")

    slots = [s.model_dump() for s in payload.slots]
    records = await submit_availability(driver, payload.week_start, slots, db)
    return {
        "driver_id": driver_id,
        "week_start": str(payload.week_start),
        "slots_recorded": len(records),
    }


@router.get("/{driver_id}/availability")
async def get_driver_availability(
    driver_id: int,
    week_start: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get a driver's submitted availability."""
    query = select(DriverAvailability).where(DriverAvailability.driver_id == driver_id)
    if week_start:
        query = query.where(DriverAvailability.week_start == week_start)
    result = await db.execute(query.order_by(DriverAvailability.week_start, DriverAvailability.day_of_week))
    rows = result.scalars().all()
    return [
        {
            "week_start": str(r.week_start),
            "day_of_week": r.day_of_week,
            "time_block": r.time_block.value,
            "is_available": r.is_available,
        }
        for r in rows
    ]


@router.post("/schedule/build")
async def build_schedule(week_start: date, db: AsyncSession = Depends(get_db)):
    """
    Build the shift schedule for a given week (admin/agent triggered).
    Runs the greedy coverage algorithm.
    """
    summary = await build_weekly_schedule(week_start, db)
    return summary


@router.post("/schedule/send")
async def send_schedule(week_start: date, db: AsyncSession = Depends(get_db)):
    """Send the built schedule to all active drivers via SMS + email."""
    count = await send_weekly_schedule(week_start, db)
    return {"drivers_notified": count, "week_start": str(week_start)}


@router.get("/schedule/week")
async def get_week_schedule(week_start: date, db: AsyncSession = Depends(get_db)):
    """Get all shifts and assignments for a given week."""
    result = await db.execute(
        select(Shift, ShiftAssignment, Driver)
        .outerjoin(ShiftAssignment, ShiftAssignment.shift_id == Shift.id)
        .outerjoin(Driver, Driver.id == ShiftAssignment.driver_id)
        .where(
            and_(
                Shift.shift_date >= week_start,
                Shift.shift_date < week_start.replace(day=week_start.day + 7),
            )
        )
        .order_by(Shift.shift_date, Shift.city, Shift.time_block)
    )
    rows = result.all()

    # Group by shift
    shifts: dict[int, dict] = {}
    for shift, assignment, driver in rows:
        if shift.id not in shifts:
            shifts[shift.id] = {
                "shift_id": shift.id,
                "date": str(shift.shift_date),
                "city": shift.city.value,
                "time_block": shift.time_block.value,
                "required": shift.required_drivers,
                "drivers": [],
            }
        if driver:
            shifts[shift.id]["drivers"].append({
                "driver_id": driver.id,
                "name": driver.full_name,
                "status": assignment.status.value,
            })

    return list(shifts.values())
