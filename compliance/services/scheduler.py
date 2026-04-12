"""
APScheduler setup for compliance agent.
Runs daily sweep at 6am, weekly report on Mondays at 6:30am.
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="America/Regina")


def setup_jobs():
    from compliance.services.sweep import run_daily_sweep
    from compliance.services.report import generate_weekly_report

    scheduler.add_job(
        run_daily_sweep,
        CronTrigger(hour=6, minute=0),
        id="daily_compliance_sweep",
        replace_existing=True,
        name="Daily Compliance Sweep",
    )

    scheduler.add_job(
        generate_weekly_report,
        CronTrigger(day_of_week="mon", hour=6, minute=30),
        id="weekly_compliance_report",
        replace_existing=True,
        name="Weekly Compliance Report",
    )

    logger.info("Compliance jobs scheduled.")
