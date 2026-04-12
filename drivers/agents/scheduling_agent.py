"""
Scheduling Agent.

Responsibilities:
- Accept driver availability submissions for upcoming week
- Build the shift schedule ensuring minimum coverage per city per time block
- Send schedule to all drivers every Sunday
- Track shift confirmations
"""
import logging
from datetime import date, datetime, timedelta
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.driver import Driver, DriverStatus, City
from models.schedule import (
    DriverAvailability, Shift, ShiftAssignment, ShiftStatus, TimeBlock
)
from services.sms import send_sms
from services.email import send_email
from config import settings

logger = logging.getLogger(__name__)

# Day blocks classified as "day" (08:00-20:00) or "night" (20:00-08:00)
DAY_BLOCKS = {TimeBlock.BLOCK_08_12, TimeBlock.BLOCK_12_16, TimeBlock.BLOCK_16_20}
NIGHT_BLOCKS = {TimeBlock.BLOCK_00_04, TimeBlock.BLOCK_04_08, TimeBlock.BLOCK_20_24}


def _next_monday() -> date:
    today = date.today()
    days_ahead = (7 - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead)


def _week_dates(week_start: date) -> list[date]:
    return [week_start + timedelta(days=i) for i in range(7)]


def _min_drivers(city: City, block: TimeBlock) -> int:
    if block in DAY_BLOCKS:
        return (
            settings.min_drivers_saskatoon_day
            if city == City.SASKATOON
            else settings.min_drivers_regina_day
        )
    return (
        settings.min_drivers_saskatoon_night
        if city == City.SASKATOON
        else settings.min_drivers_regina_night
    )


async def submit_availability(
    driver: Driver,
    week_start: date,
    slots: list[dict],  # [{"day_of_week": 0..6, "time_block": TimeBlock, "is_available": bool}]
    db: AsyncSession,
) -> list[DriverAvailability]:
    """Record a driver's availability for the given week."""
    records = []
    for slot in slots:
        # Upsert
        result = await db.execute(
            select(DriverAvailability).where(
                and_(
                    DriverAvailability.driver_id == driver.id,
                    DriverAvailability.week_start == week_start,
                    DriverAvailability.day_of_week == slot["day_of_week"],
                    DriverAvailability.time_block == slot["time_block"],
                )
            )
        )
        avail = result.scalar_one_or_none()
        if avail:
            avail.is_available = slot.get("is_available", True)
        else:
            avail = DriverAvailability(
                driver_id=driver.id,
                week_start=week_start,
                day_of_week=slot["day_of_week"],
                time_block=slot["time_block"],
                is_available=slot.get("is_available", True),
            )
            db.add(avail)
        records.append(avail)

    await db.commit()
    logger.info(
        f"Driver {driver.id} submitted {len(records)} availability slots "
        f"for week {week_start}"
    )
    return records


async def build_weekly_schedule(week_start: date, db: AsyncSession) -> dict:
    """
    Build the schedule for the coming week.
    For each city × day × time_block, create a Shift and assign available drivers
    until minimum coverage is met. Greedy approach — prefers drivers with fewer
    assignments this week (fair distribution).

    Returns a summary dict.
    """
    all_dates = _week_dates(week_start)
    cities = list(City)
    blocks = list(TimeBlock)

    # Fetch all active drivers
    result = await db.execute(
        select(Driver).where(Driver.status == DriverStatus.ACTIVE)
    )
    active_drivers = list(result.scalars().all())

    # Fetch all availability for this week
    result = await db.execute(
        select(DriverAvailability).where(DriverAvailability.week_start == week_start)
    )
    avail_rows = list(result.scalars().all())

    # Build lookup: driver_id → set of (day_of_week, time_block)
    avail_map: dict[int, set] = {}
    for row in avail_rows:
        if row.is_available:
            avail_map.setdefault(row.driver_id, set()).add(
                (row.day_of_week, row.time_block)
            )

    # Track assignments per driver this week (for fairness)
    assignment_count: dict[int, int] = {d.id: 0 for d in active_drivers}

    shifts_created = 0
    assignments_made = 0
    coverage_gaps = []

    for shift_date in all_dates:
        dow = shift_date.weekday()
        for city in cities:
            city_drivers = [d for d in active_drivers if d.city == city]
            for block in blocks:
                min_required = _min_drivers(city, block)

                # Check if shift already exists
                existing = await db.execute(
                    select(Shift).where(
                        and_(
                            Shift.city == city,
                            Shift.shift_date == shift_date,
                            Shift.time_block == block,
                        )
                    )
                )
                shift = existing.scalar_one_or_none()
                if not shift:
                    shift = Shift(
                        city=city,
                        shift_date=shift_date,
                        time_block=block,
                        required_drivers=min_required,
                    )
                    db.add(shift)
                    await db.flush()
                    shifts_created += 1

                # Find available drivers for this slot, sorted by fewest assignments
                candidates = [
                    d for d in city_drivers
                    if (dow, block) in avail_map.get(d.id, set())
                ]
                candidates.sort(key=lambda d: assignment_count[d.id])

                # How many already assigned?
                existing_assignments = await db.execute(
                    select(ShiftAssignment).where(ShiftAssignment.shift_id == shift.id)
                )
                already = len(list(existing_assignments.scalars().all()))

                needed = max(0, min_required - already)
                assigned_now = 0
                for driver in candidates[:needed]:
                    # Check not already in this shift
                    dup = await db.execute(
                        select(ShiftAssignment).where(
                            and_(
                                ShiftAssignment.shift_id == shift.id,
                                ShiftAssignment.driver_id == driver.id,
                            )
                        )
                    )
                    if dup.scalar_one_or_none():
                        continue
                    sa = ShiftAssignment(shift_id=shift.id, driver_id=driver.id)
                    db.add(sa)
                    assignment_count[driver.id] += 1
                    assigned_now += 1
                    assignments_made += 1

                if already + assigned_now < min_required:
                    coverage_gaps.append(
                        f"{shift_date} {city.value} {block.value}: "
                        f"only {already + assigned_now}/{min_required} drivers"
                    )

    await db.commit()
    logger.info(
        f"Schedule built for week {week_start}: "
        f"{shifts_created} shifts, {assignments_made} assignments, "
        f"{len(coverage_gaps)} gaps"
    )

    if coverage_gaps:
        gap_text = "\n".join(coverage_gaps[:10])
        await send_sms(
            settings.owner_phone,
            f"Captain Taxi schedule alert — {len(coverage_gaps)} coverage gaps "
            f"for week {week_start}:\n{gap_text}"
        )

    return {
        "week_start": str(week_start),
        "shifts_created": shifts_created,
        "assignments_made": assignments_made,
        "coverage_gaps": coverage_gaps,
    }


async def send_weekly_schedule(week_start: date, db: AsyncSession) -> int:
    """
    Send each active driver their personal schedule for the week via SMS + email.
    Returns count of drivers notified.
    """
    result = await db.execute(
        select(Driver).where(Driver.status == DriverStatus.ACTIVE)
    )
    drivers = list(result.scalars().all())

    notified = 0
    for driver in drivers:
        # Fetch their assignments for the week
        result = await db.execute(
            select(ShiftAssignment, Shift)
            .join(Shift, ShiftAssignment.shift_id == Shift.id)
            .where(
                and_(
                    ShiftAssignment.driver_id == driver.id,
                    Shift.shift_date >= week_start,
                    Shift.shift_date < week_start + timedelta(days=7),
                )
            )
            .order_by(Shift.shift_date, Shift.time_block)
        )
        rows = result.all()

        if not rows:
            sms_body = (
                f"Hi {driver.first_name}, you have no shifts scheduled for the week "
                f"of {week_start}. Please submit your availability if you'd like to work."
            )
            schedule_lines = ["No shifts scheduled."]
        else:
            schedule_lines = []
            for sa, shift in rows:
                day_name = shift.shift_date.strftime("%A %b %d")
                schedule_lines.append(f"  {day_name}: {shift.time_block.value}")
                sa.notified_at = sa.notified_at or datetime.utcnow()

            sms_body = (
                f"Hi {driver.first_name}! Your Captain Taxi schedule for {week_start}:\n"
                + "\n".join(schedule_lines)
                + "\nReply SCHEDULE to see this again any time."
            )

        await send_sms(driver.phone, sms_body)

        schedule_html = "".join(f"<li>{line}</li>" for line in schedule_lines)
        await send_email(
            to=driver.email,
            subject=f"Your Captain Taxi Schedule — Week of {week_start}",
            html_body=f"""
            <div style="font-family:Arial,sans-serif;max-width:600px">
              <h2>Your Schedule for {week_start}</h2>
              <p>Hi {driver.first_name},</p>
              <ul>{schedule_html}</ul>
              <p>Text SCHEDULE to {settings.twilio_phone_number} to retrieve this any time.</p>
            </div>
            """,
        )
        notified += 1

    await db.commit()
    logger.info(f"Schedule sent to {notified} drivers for week {week_start}")
    return notified
