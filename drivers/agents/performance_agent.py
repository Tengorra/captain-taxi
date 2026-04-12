"""
Performance Tracking Agent.

Responsibilities:
- Ingest weekly metrics per driver (from dispatch system or manual)
- Generate weekly performance reports
- Detect threshold breaches and raise PerformanceFlags
- Send warning messages to flagged drivers
- Escalate repeat offenders to owner
"""
import logging
from datetime import date, timedelta
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.driver import Driver, DriverStatus
from models.performance import (
    DriverMetrics, PerformanceFlag, Complaint, FlagType, FlagStatus
)
from services.sms import send_sms
from services.email import send_email, performance_report_html
from config import settings

logger = logging.getLogger(__name__)


async def record_weekly_metrics(
    driver: Driver,
    week_start: date,
    trips_completed: int,
    trips_cancelled: int,
    trips_offered: int,
    avg_rating: float | None,
    late_arrivals: int,
    income_earned: float,
    hours_online: float,
    db: AsyncSession,
) -> DriverMetrics:
    """Upsert weekly metrics and trigger analysis."""
    # Check for existing record
    result = await db.execute(
        select(DriverMetrics).where(
            and_(
                DriverMetrics.driver_id == driver.id,
                DriverMetrics.week_start == week_start,
            )
        )
    )
    metrics = result.scalar_one_or_none()

    cancel_rate = (
        trips_cancelled / trips_offered if trips_offered > 0 else 0.0
    )

    if metrics:
        metrics.trips_completed = trips_completed
        metrics.trips_cancelled = trips_cancelled
        metrics.trips_offered = trips_offered
        metrics.avg_rating = avg_rating
        metrics.late_arrivals = late_arrivals
        metrics.income_earned = income_earned
        metrics.hours_online = hours_online
        metrics.cancellation_rate = cancel_rate
    else:
        metrics = DriverMetrics(
            driver_id=driver.id,
            week_start=week_start,
            trips_completed=trips_completed,
            trips_cancelled=trips_cancelled,
            trips_offered=trips_offered,
            avg_rating=avg_rating,
            late_arrivals=late_arrivals,
            income_earned=income_earned,
            hours_online=hours_online,
            cancellation_rate=cancel_rate,
        )
        db.add(metrics)

    await db.flush()
    await _check_thresholds(driver, metrics, db)
    await db.commit()
    return metrics


async def _check_thresholds(
    driver: Driver, metrics: DriverMetrics, db: AsyncSession
) -> None:
    """Raise flags for any metric breaching thresholds."""
    checks = []

    if metrics.cancellation_rate is not None and metrics.cancellation_rate > settings.cancellation_rate_threshold:
        checks.append((
            FlagType.HIGH_CANCELLATION,
            metrics.cancellation_rate,
            f"Cancellation rate {metrics.cancellation_rate:.1%} exceeds "
            f"{settings.cancellation_rate_threshold:.0%} threshold",
        ))

    if metrics.avg_rating is not None and metrics.avg_rating < settings.rating_threshold:
        checks.append((
            FlagType.LOW_RATING,
            metrics.avg_rating,
            f"Average rating {metrics.avg_rating:.2f} is below {settings.rating_threshold}",
        ))

    # Check complaints in rolling 30-day window
    cutoff = date.today() - timedelta(days=settings.complaint_threshold_days)
    complaint_count_result = await db.execute(
        select(func.count()).select_from(Complaint).where(
            and_(
                Complaint.driver_id == driver.id,
                Complaint.created_at >= cutoff,
            )
        )
    )
    complaint_count = complaint_count_result.scalar() or 0
    if complaint_count >= settings.complaint_threshold_count:
        checks.append((
            FlagType.EXCESSIVE_COMPLAINTS,
            float(complaint_count),
            f"{complaint_count} complaints in the last {settings.complaint_threshold_days} days",
        ))

    for flag_type, value, detail in checks:
        await _raise_flag(driver, flag_type, value, detail, metrics.week_start, db)


async def _raise_flag(
    driver: Driver,
    flag_type: FlagType,
    value: float,
    detail: str,
    week_start: date,
    db: AsyncSession,
) -> None:
    # Check if there's already an open flag of this type
    existing = await db.execute(
        select(PerformanceFlag).where(
            and_(
                PerformanceFlag.driver_id == driver.id,
                PerformanceFlag.flag_type == flag_type,
                PerformanceFlag.status.in_([FlagStatus.OPEN, FlagStatus.WARNING_SENT]),
            )
        )
    )
    existing_flag = existing.scalar_one_or_none()

    if existing_flag:
        # Already warned — escalate if not already done
        if existing_flag.status == FlagStatus.WARNING_SENT:
            await _escalate_flag(driver, existing_flag, db)
        return

    # New flag
    flag = PerformanceFlag(
        driver_id=driver.id,
        flag_type=flag_type,
        value=value,
        detail=detail,
        week_start=week_start,
        status=FlagStatus.OPEN,
    )
    db.add(flag)
    await db.flush()
    await _send_warning(driver, flag, db)


async def _send_warning(
    driver: Driver, flag: PerformanceFlag, db: AsyncSession
) -> None:
    from datetime import datetime
    type_messages = {
        FlagType.HIGH_CANCELLATION: (
            f"your cancellation rate this week was {flag.value:.1%}, which exceeds our "
            f"acceptable threshold of {settings.cancellation_rate_threshold:.0%}."
        ),
        FlagType.LOW_RATING: (
            f"your average passenger rating is {flag.value:.2f}, which is below our "
            f"minimum standard of {settings.rating_threshold}."
        ),
        FlagType.EXCESSIVE_COMPLAINTS: (
            f"you have received {int(flag.value)} complaints in the last "
            f"{settings.complaint_threshold_days} days."
        ),
        FlagType.LATE_ARRIVALS: (
            f"you have had {int(flag.value)} late arrivals recently."
        ),
    }
    reason = type_messages.get(flag.flag_type, flag.detail or "performance concern")

    sms_body = (
        f"Hi {driver.first_name}, this is a performance notice from Captain Taxi. "
        f"We've noticed {reason} Please review and improve. "
        "Reply HELP or call your supervisor if you have questions."
    )
    await send_sms(driver.phone, sms_body)
    await send_email(
        to=driver.email,
        subject="Captain Taxi — Performance Notice",
        html_body=f"""
        <div style="font-family:Arial,sans-serif;max-width:600px">
          <h2 style="color:#e63946">Performance Notice</h2>
          <p>Hi {driver.first_name},</p>
          <p>We've identified a performance concern: <strong>{reason}</strong></p>
          <p>We value you as a driver and want to support your success.
             Please make the necessary improvements. Continued issues may result in
             further action.</p>
          <p>Contact us if you have questions.</p>
        </div>
        """,
    )

    flag.status = FlagStatus.WARNING_SENT
    flag.warning_sent_at = datetime.utcnow()
    logger.info(f"Performance warning sent to driver {driver.id} for {flag.flag_type}")


async def _escalate_flag(
    driver: Driver, flag: PerformanceFlag, db: AsyncSession
) -> None:
    from datetime import datetime

    flag.status = FlagStatus.ESCALATED
    flag.escalated_at = datetime.utcnow()

    msg = (
        f"Captain Taxi ESCALATION: Driver {driver.full_name} (ID {driver.id}) "
        f"has a repeat {flag.flag_type.value} flag. "
        f"Detail: {flag.detail}. "
        f"Review: {settings.base_url}/admin/drivers/{driver.id}"
    )
    await send_sms(settings.owner_phone, msg)
    await send_email(
        to=settings.owner_email,
        subject=f"Escalation: Driver Performance — {driver.full_name}",
        html_body=f"""
        <div style="font-family:Arial,sans-serif;max-width:600px">
          <h2 style="color:#e63946">Driver Performance Escalation</h2>
          <p>Driver <strong>{driver.full_name}</strong> has a repeat performance issue
             that requires your attention.</p>
          <p><strong>Issue:</strong> {flag.flag_type.value}</p>
          <p><strong>Detail:</strong> {flag.detail}</p>
          <a href="{settings.base_url}/admin/drivers/{driver.id}"
             style="background:#e63946;color:#fff;padding:10px 20px;
                    border-radius:4px;text-decoration:none;display:inline-block">
            View Driver Profile
          </a>
        </div>
        """,
    )
    logger.warning(
        f"Performance flag escalated to owner for driver {driver.id} ({driver.full_name})"
    )


async def send_weekly_report(driver: Driver, week_start: date, db: AsyncSession) -> bool:
    """Send a driver their weekly performance report. Returns True if sent."""
    result = await db.execute(
        select(DriverMetrics).where(
            and_(
                DriverMetrics.driver_id == driver.id,
                DriverMetrics.week_start == week_start,
            )
        )
    )
    metrics = result.scalar_one_or_none()
    if not metrics:
        return False

    metrics_dict = {
        "trips_completed": metrics.trips_completed,
        "cancellation_rate": metrics.cancellation_rate,
        "avg_rating": metrics.avg_rating,
        "income_earned": metrics.income_earned,
        "hours_online": metrics.hours_online,
    }

    week_label = week_start.strftime("%B %d, %Y")
    cancel_pct = (metrics.cancellation_rate or 0) * 100

    sms_body = (
        f"Captain Taxi weekly report ({week_label}): "
        f"{metrics.trips_completed} trips, "
        f"{cancel_pct:.0f}% cancel rate, "
        f"Rating: {metrics.avg_rating or 'N/A'}, "
        f"Earned: ${metrics.income_earned:.0f}"
    )
    await send_sms(driver.phone, sms_body)
    await send_email(
        to=driver.email,
        subject=f"Your Captain Taxi Weekly Report — {week_label}",
        html_body=performance_report_html(driver.first_name, week_label, metrics_dict),
    )

    from datetime import datetime
    metrics.report_sent = True
    metrics.report_sent_at = datetime.utcnow()
    await db.commit()
    return True


async def add_complaint(
    driver: Driver,
    source: str,
    description: str,
    severity: int = 1,
    trip_id: str | None = None,
    db: AsyncSession = None,
) -> Complaint:
    complaint = Complaint(
        driver_id=driver.id,
        source=source,
        description=description,
        severity=severity,
        trip_id=trip_id,
    )
    db.add(complaint)
    await db.flush()

    # Immediately re-check complaint threshold
    await _check_thresholds(driver, _dummy_metrics(driver), db)
    await db.commit()
    return complaint


def _dummy_metrics(driver: Driver) -> DriverMetrics:
    """Placeholder metrics object used when checking complaints outside weekly cycle."""
    m = DriverMetrics.__new__(DriverMetrics)
    m.driver_id = driver.id
    m.week_start = date.today()
    m.trips_completed = 0
    m.trips_cancelled = 0
    m.trips_offered = 0
    m.avg_rating = None
    m.late_arrivals = 0
    m.income_earned = 0.0
    m.hours_online = 0.0
    m.cancellation_rate = None
    return m
