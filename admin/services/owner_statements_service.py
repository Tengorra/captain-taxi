"""
Owner-statement roll-up service.

Groups completed trips for a given period by the driver's `vehicle_ref`,
sums the gross fares, applies the company commission (from the Settings
table, defaults to 30%) as a deduction, and writes a draft OwnerStatement
per vehicle_ref. Idempotent: skips vehicle_refs that already have a
statement for the exact (period_start, period_end) pair.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
from calendar import monthrange
import logging

from sqlalchemy import and_

from ..db.database import SessionLocal
from ..db.models import Trip, Driver, OwnerStatement, Settings

logger = logging.getLogger(__name__)


def _commission_rate(db) -> float:
    """Read company commission rate from Settings (avg of Saskatoon/Regina rows)."""
    rates = []
    for key in ("commission_rate_saskatoon", "commission_rate_regina"):
        row = db.query(Settings).filter_by(key=key).first()
        if row:
            try:
                rates.append(float(row.value))
            except (TypeError, ValueError):
                pass
    return sum(rates) / len(rates) if rates else 0.30


def last_full_month() -> tuple[date, date]:
    """Return (first_day, last_day) of the calendar month before today."""
    today = date.today()
    first_of_this = today.replace(day=1)
    last_of_prev = first_of_this - timedelta(days=1)
    first_of_prev = last_of_prev.replace(day=1)
    return first_of_prev, last_of_prev


def generate_for_period(period_start: date, period_end: date) -> dict:
    """Generate (or refresh-skip) OwnerStatement rows for every vehicle_ref
    that had completed trips in the window. Returns a summary dict."""
    db = SessionLocal()
    created: list[int] = []
    skipped: list[str] = []
    try:
        rate = _commission_rate(db)
        # Pull completed trips in the window, joined to driver.vehicle_ref.
        rows = (
            db.query(Trip, Driver)
            .join(Driver, Driver.id == Trip.driver_id)
            .filter(
                Trip.status == "completed",
                and_(
                    Trip.completed_at >= datetime.combine(period_start, datetime.min.time(), tzinfo=timezone.utc),
                    Trip.completed_at <  datetime.combine(period_end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc),
                ),
            )
            .all()
        )

        by_vehicle: dict[str, dict] = {}
        for trip, driver in rows:
            vref = driver.vehicle_ref or "unassigned"
            slot = by_vehicle.setdefault(vref, {
                "vehicle_ref": vref,
                "owner_name": driver.name or "Unknown",  # fallback — real owner mapping is future work
                "owner_email": driver.email,
                "gross": 0.0,
                "trip_count": 0,
            })
            slot["gross"] += trip.fare or 0.0
            slot["trip_count"] += 1

        for vref, data in by_vehicle.items():
            existing = db.query(OwnerStatement).filter_by(
                vehicle_ref=vref,
                period_start=period_start,
                period_end=period_end,
            ).first()
            if existing:
                skipped.append(vref)
                continue

            gross = round(data["gross"], 2)
            deductions = round(gross * rate, 2)
            net = round(gross - deductions, 2)
            stmt = OwnerStatement(
                owner_name=data["owner_name"],
                owner_email=data["owner_email"],
                vehicle_ref=vref,
                period_start=period_start,
                period_end=period_end,
                gross=gross,
                deductions=deductions,
                net=net,
                status="draft",
                notes=f"Auto-generated from {data['trip_count']} completed trip(s) @ {int(rate*100)}% company commission.",
            )
            db.add(stmt)
            db.flush()
            created.append(stmt.id)

        db.commit()
        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "commission_rate": rate,
            "created_count": len(created),
            "skipped_count": len(skipped),
            "created_ids": created,
            "skipped_vehicle_refs": skipped,
        }
    finally:
        db.close()


def generate_for_last_month() -> dict:
    """Convenience wrapper used by the monthly scheduler."""
    start, end = last_full_month()
    logger.info("Generating owner statements for %s → %s", start, end)
    return generate_for_period(start, end)
