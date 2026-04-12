"""
APScheduler setup — registers all recurring jobs.
Jobs are started when the FastAPI app starts.
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="America/Regina")


def setup_jobs():
    """Register all scheduled jobs. Called once at startup."""

    # Sunday 8:00 PM — build next week's schedule from submitted availability
    scheduler.add_job(
        _build_and_send_schedule,
        CronTrigger(day_of_week="sun", hour=20, minute=0),
        id="weekly_schedule_build",
        replace_existing=True,
        name="Build & send weekly driver schedule",
    )

    # Monday 8:00 AM — send weekly performance reports for prior week
    scheduler.add_job(
        _send_weekly_reports,
        CronTrigger(day_of_week="mon", hour=8, minute=0),
        id="weekly_performance_reports",
        replace_existing=True,
        name="Send weekly performance reports",
    )

    # Wednesday 10:00 AM — remind drivers who haven't submitted availability
    scheduler.add_job(
        _availability_reminders,
        CronTrigger(day_of_week="wed", hour=10, minute=0),
        id="availability_reminders",
        replace_existing=True,
        name="Availability submission reminders",
    )

    # Daily 9:00 AM — onboarding reminders for incomplete drivers
    scheduler.add_job(
        _onboarding_reminders,
        CronTrigger(hour=9, minute=0),
        id="onboarding_reminders",
        replace_existing=True,
        name="Daily onboarding reminders",
    )

    # Daily 6:00 AM — check expiring documents (licenses, insurance)
    scheduler.add_job(
        _document_expiry_check,
        CronTrigger(hour=6, minute=0),
        id="document_expiry_check",
        replace_existing=True,
        name="Document expiry check",
    )

    logger.info("All scheduled jobs registered.")


async def _build_and_send_schedule():
    from tasks.weekly_jobs import build_and_send_schedule
    await build_and_send_schedule()


async def _send_weekly_reports():
    from tasks.weekly_jobs import send_weekly_performance_reports
    await send_weekly_performance_reports()


async def _availability_reminders():
    from tasks.weekly_jobs import send_availability_reminders
    await send_availability_reminders()


async def _onboarding_reminders():
    from tasks.weekly_jobs import send_onboarding_reminders
    await send_onboarding_reminders()


async def _document_expiry_check():
    from tasks.weekly_jobs import check_document_expiry
    await check_document_expiry()
