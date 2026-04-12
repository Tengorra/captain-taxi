"""
Driver Pay Service
==================
Every Friday at 11 PM:
  1. Pull all completed trips for Mon–Sun.
  2. Calculate each active driver's earnings (75 % of fares + tips).
  3. Create a DriverPayment record.
  4. Push a contractor Bill to QuickBooks.
  5. SMS the driver their pay stub.
"""
import logging
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from config import settings
from models.driver import Driver, DriverStatus
from models.trip import Trip, TripStatus
from models.payment import DriverPayment, PaymentStatus
import services.quickbooks as qb_service
import services.notifications as notify

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal("0.01")


def _get_week_range(ref_date: date | None = None) -> tuple[date, date]:
    """Return (Monday, Sunday) for the week containing ref_date (default: last full week)."""
    today = ref_date or date.today()
    # Last Monday
    monday = today - timedelta(days=today.weekday() + 7)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def calculate_driver_pay(
    db: Session,
    driver: Driver,
    week_start: date,
    week_end: date,
) -> dict:
    """Return pay breakdown dict for one driver over a week. Does NOT write to DB."""
    trips = (
        db.query(Trip)
        .filter(
            Trip.driver_id == driver.id,
            Trip.status == TripStatus.COMPLETED,
            func.date(Trip.completed_at) >= week_start,
            func.date(Trip.completed_at) <= week_end,
        )
        .all()
    )

    total_fares = sum(t.fare for t in trips) or Decimal("0.00")
    total_tips = sum(t.tip for t in trips) or Decimal("0.00")
    total_trips = len(trips)

    rate = driver.commission_rate or settings.driver_commission_rate
    driver_earnings = (total_fares * rate).quantize(TWO_PLACES, ROUND_HALF_UP)
    company_cut = (total_fares * (1 - rate)).quantize(TWO_PLACES, ROUND_HALF_UP)
    net_pay = (driver_earnings + total_tips).quantize(TWO_PLACES, ROUND_HALF_UP)

    return {
        "driver": driver,
        "week_start": week_start,
        "week_end": week_end,
        "total_fares": total_fares,
        "total_trips": total_trips,
        "commission_rate": rate,
        "driver_earnings": driver_earnings,
        "company_cut": company_cut,
        "tips": total_tips,
        "net_pay": net_pay,
    }


def run_weekly_payroll(db: Session, week_start: date | None = None) -> list[DriverPayment]:
    """
    Main payroll job — called by scheduler every Friday night.
    Returns list of DriverPayment records created.
    """
    mon, sun = _get_week_range(week_start)
    logger.info("Running payroll for week %s – %s", mon, sun)

    # Skip if already run for this week
    existing = db.query(DriverPayment).filter_by(week_start=mon).first()
    if existing:
        logger.warning("Payroll already processed for week starting %s — skipping", mon)
        return []

    drivers = db.query(Driver).filter_by(status=DriverStatus.ACTIVE).all()
    payments: list[DriverPayment] = []

    for driver in drivers:
        pay = calculate_driver_pay(db, driver, mon, sun)
        if pay["total_trips"] == 0:
            logger.debug("Driver %s had 0 trips this week — skipping", driver.full_name)
            continue

        # Ensure QB vendor exists
        if not driver.qb_vendor_id:
            try:
                driver.qb_vendor_id = qb_service.ensure_driver_vendor(
                    db, driver_id=driver.id, full_name=driver.full_name, email=driver.email
                )
                db.commit()
            except Exception as exc:
                logger.error("QB vendor creation failed for %s: %s", driver.full_name, exc)

        # Create DB record
        record = DriverPayment(
            driver_id=driver.id,
            week_start=mon,
            week_end=sun,
            total_fares=pay["total_fares"],
            total_trips=pay["total_trips"],
            commission_rate=pay["commission_rate"],
            driver_earnings=pay["driver_earnings"],
            company_cut=pay["company_cut"],
            tips=pay["tips"],
            net_pay=pay["net_pay"],
            status=PaymentStatus.PENDING,
        )
        db.add(record)
        db.flush()  # get ID

        # Push to QB
        if driver.qb_vendor_id:
            try:
                bill_id = qb_service.push_driver_payment(
                    db,
                    driver_qb_vendor_id=driver.qb_vendor_id,
                    driver_name=driver.full_name,
                    amount=pay["net_pay"],
                    week_start=mon.isoformat(),
                    week_end=sun.isoformat(),
                )
                record.qb_bill_id = bill_id
                record.status = PaymentStatus.SENT
            except Exception as exc:
                logger.error("QB bill push failed for %s: %s", driver.full_name, exc)

        db.commit()

        # Send SMS pay stub
        if driver.phone:
            try:
                msg = _format_pay_stub_sms(pay)
                sid = notify.send_sms(driver.phone, msg)
                record.sms_sent_at = __import__("datetime").datetime.utcnow()
                record.sms_message_sid = sid
                db.commit()
            except Exception as exc:
                logger.error("SMS failed for %s: %s", driver.full_name, exc)

        payments.append(record)
        logger.info(
            "Payroll processed: %s — %d trips — $%s net pay",
            driver.full_name, pay["total_trips"], pay["net_pay"]
        )

    return payments


def _format_pay_stub_sms(pay: dict) -> str:
    mon = pay["week_start"].strftime("%b %d")
    sun = pay["week_end"].strftime("%b %d")
    rate_pct = int(pay["commission_rate"] * 100)
    return (
        f"Captain Taxi — Pay Stub\n"
        f"Week: {mon} – {sun}\n"
        f"Trips: {pay['total_trips']}\n"
        f"Fares: ${pay['total_fares']:.2f}\n"
        f"Your share ({rate_pct}%): ${pay['driver_earnings']:.2f}\n"
        f"Tips: ${pay['tips']:.2f}\n"
        f"NET PAY: ${pay['net_pay']:.2f}\n"
        f"Questions? Reply HELP"
    )
