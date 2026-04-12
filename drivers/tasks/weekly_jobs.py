"""
All recurring background jobs.
Each function gets its own DB session so failures are isolated.
"""
import logging
from datetime import date, datetime, timedelta
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from models.driver import Driver, DriverStatus, DriverDocument
from models.schedule import DriverAvailability
from models.performance import DriverMetrics
from agents.onboarding_agent import send_onboarding_reminder
from agents.scheduling_agent import build_weekly_schedule, send_weekly_schedule
from agents.performance_agent import send_weekly_report
from services.sms import send_sms
from services.email import send_email
from config import settings

logger = logging.getLogger(__name__)


def _next_monday() -> date:
    today = date.today()
    days = (7 - today.weekday()) % 7
    return today + timedelta(days=days if days else 7)


def _last_monday() -> date:
    today = date.today()
    return today - timedelta(days=today.weekday())


async def build_and_send_schedule():
    """Sunday job: build schedule for the coming week, then notify all drivers."""
    week_start = _next_monday()
    logger.info(f"[JOB] Building schedule for week {week_start}")
    async with AsyncSessionLocal() as db:
        try:
            summary = await build_weekly_schedule(week_start, db)
            logger.info(f"[JOB] Schedule built: {summary}")
            notified = await send_weekly_schedule(week_start, db)
            logger.info(f"[JOB] Schedule sent to {notified} drivers")
        except Exception as e:
            logger.error(f"[JOB] build_and_send_schedule failed: {e}", exc_info=True)


async def send_weekly_performance_reports():
    """Monday job: send performance reports for the previous week to all active drivers."""
    week_start = _last_monday() - timedelta(weeks=1)
    logger.info(f"[JOB] Sending performance reports for week {week_start}")
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(Driver).where(Driver.status == DriverStatus.ACTIVE)
            )
            drivers = result.scalars().all()
            sent = 0
            for driver in drivers:
                ok = await send_weekly_report(driver, week_start, db)
                if ok:
                    sent += 1
            logger.info(f"[JOB] Performance reports sent to {sent}/{len(drivers)} drivers")
        except Exception as e:
            logger.error(f"[JOB] send_weekly_performance_reports failed: {e}", exc_info=True)


async def send_availability_reminders():
    """
    Wednesday job: remind active drivers who haven't submitted availability
    for the coming week.
    """
    week_start = _next_monday()
    logger.info(f"[JOB] Sending availability reminders for week {week_start}")
    async with AsyncSessionLocal() as db:
        try:
            # Find drivers who haven't submitted any availability for next week
            submitted_ids_result = await db.execute(
                select(DriverAvailability.driver_id.distinct())
                .where(DriverAvailability.week_start == week_start)
            )
            submitted_ids = {row[0] for row in submitted_ids_result.all()}

            result = await db.execute(
                select(Driver).where(Driver.status == DriverStatus.ACTIVE)
            )
            drivers = result.scalars().all()

            reminded = 0
            for driver in drivers:
                if driver.id not in submitted_ids:
                    msg = (
                        f"Hi {driver.first_name}! Please submit your availability for "
                        f"the week of {week_start} by Friday. "
                        f"Log in at {settings.base_url}/driver-portal/{driver.id} "
                        "or text AVAILABLE/OFFLINE each day."
                    )
                    await send_sms(driver.phone, msg)
                    reminded += 1

            logger.info(
                f"[JOB] Availability reminders sent to {reminded} drivers "
                f"(week {week_start})"
            )
        except Exception as e:
            logger.error(f"[JOB] send_availability_reminders failed: {e}", exc_info=True)


async def send_onboarding_reminders():
    """Daily job: nudge drivers who are still in onboarding."""
    logger.info("[JOB] Sending onboarding reminders")
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(Driver).where(
                    and_(
                        Driver.status == DriverStatus.ONBOARDING,
                        Driver.onboarding_completion < 1.0,
                    )
                )
            )
            drivers = result.scalars().all()
            reminded = 0
            for driver in drivers:
                # Only remind every 2 days to avoid spamming
                if driver.onboarding_reminder_count == 0 or (
                    driver.updated_at
                    and (datetime.utcnow() - driver.updated_at).days >= 2
                ):
                    await send_onboarding_reminder(driver, db)
                    reminded += 1

            logger.info(f"[JOB] Onboarding reminders sent to {reminded} drivers")
        except Exception as e:
            logger.error(f"[JOB] send_onboarding_reminders failed: {e}", exc_info=True)


async def check_document_expiry():
    """
    Daily job: check for documents expiring within 30 days.
    Notify the driver and owner.
    """
    logger.info("[JOB] Checking document expiry")
    async with AsyncSessionLocal() as db:
        try:
            today = date.today()
            warn_date = today + timedelta(days=30)

            result = await db.execute(
                select(DriverDocument, Driver)
                .join(Driver, Driver.id == DriverDocument.driver_id)
                .where(
                    and_(
                        DriverDocument.expiry_date.isnot(None),
                        DriverDocument.expiry_date <= warn_date,
                        DriverDocument.expiry_date >= today,
                        Driver.status == DriverStatus.ACTIVE,
                    )
                )
            )
            rows = result.all()

            owner_alerts = []
            for doc, driver in rows:
                days_left = (doc.expiry_date.date() - today).days
                doc_label = doc.doc_type.value.replace("_", " ").title()

                await send_sms(
                    driver.phone,
                    f"Captain Taxi: Your {doc_label} expires in {days_left} day(s) "
                    f"({doc.expiry_date.strftime('%b %d, %Y')}). "
                    "Please renew and upload the updated document via the portal."
                )
                owner_alerts.append(
                    f"• {driver.full_name} — {doc_label} expires in {days_left} days"
                )

            if owner_alerts:
                summary = "\n".join(owner_alerts)
                await send_email(
                    to=settings.owner_email,
                    subject=f"Captain Taxi: {len(owner_alerts)} Document(s) Expiring Soon",
                    html_body=f"""
                    <div style="font-family:Arial,sans-serif;max-width:600px">
                      <h2>Document Expiry Alerts</h2>
                      <p>The following driver documents are expiring within 30 days:</p>
                      <pre style="background:#f4f4f4;padding:12px;border-radius:6px">
{summary}
                      </pre>
                      <a href="{settings.base_url}/admin/drivers"
                         style="background:#e63946;color:#fff;padding:10px 20px;
                                border-radius:4px;text-decoration:none">
                        Review Drivers
                      </a>
                    </div>
                    """,
                )
                logger.info(f"[JOB] Document expiry alerts: {len(owner_alerts)} documents")
            else:
                logger.info("[JOB] No documents expiring within 30 days")

        except Exception as e:
            logger.error(f"[JOB] check_document_expiry failed: {e}", exc_info=True)
