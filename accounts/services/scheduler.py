"""
APScheduler Jobs
=================
All scheduled jobs for the accounts agent.

Schedule (Saskatchewan time = UTC-6, no DST):
  - Daily   23:30 SKT (05:30 UTC next day)  → daily revenue summary
  - Friday  23:00 SKT (05:00 UTC Saturday)  → weekly payroll
  - Monday  07:00 SKT (13:00 UTC)           → weekly P&L email
  - 1st of month 06:00 SKT (12:00 UTC)      → monthly invoices + monthly report
  - Apr 1, Jul 1, Oct 1, Jan 1 06:00 SKT    → GST remittance summary
  - Feb 1 06:00 SKT                         → T4A reminder
"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from database import SessionLocal

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="America/Regina")


def _db():
    return SessionLocal()


# ─── Job Functions ────────────────────────────────────────────────────────────

def job_daily_revenue():
    from services.revenue import daily_revenue_summary
    db = _db()
    try:
        result = daily_revenue_summary(db)
        logger.info("Daily revenue job done: %d trips, $%s", result["total_trips"], result["total_fare"])
    except Exception as exc:
        logger.error("Daily revenue job failed: %s", exc)
    finally:
        db.close()


def job_weekly_payroll():
    from services.driver_pay import run_weekly_payroll
    db = _db()
    try:
        payments = run_weekly_payroll(db)
        logger.info("Weekly payroll job done: %d drivers paid", len(payments))
    except Exception as exc:
        logger.error("Weekly payroll job failed: %s", exc)
    finally:
        db.close()


def job_weekly_pnl():
    from services.revenue import weekly_pnl
    db = _db()
    try:
        weekly_pnl(db)
        logger.info("Weekly P&L job done")
    except Exception as exc:
        logger.error("Weekly P&L job failed: %s", exc)
    finally:
        db.close()


def job_monthly_invoices():
    from services.invoicing import generate_monthly_invoices
    db = _db()
    try:
        invoices = generate_monthly_invoices(db)
        logger.info("Monthly invoices job done: %d invoices generated", len(invoices))
    except Exception as exc:
        logger.error("Monthly invoices job failed: %s", exc)
    finally:
        db.close()


def job_monthly_report():
    from services.revenue import monthly_revenue_report
    db = _db()
    try:
        monthly_revenue_report(db)
        logger.info("Monthly revenue report sent")
    except Exception as exc:
        logger.error("Monthly revenue report job failed: %s", exc)
    finally:
        db.close()


def job_invoice_reminders():
    from services.invoicing import send_payment_reminders
    db = _db()
    try:
        send_payment_reminders(db)
        logger.info("Invoice reminder check done")
    except Exception as exc:
        logger.error("Invoice reminder job failed: %s", exc)
    finally:
        db.close()


def job_quarterly_gst():
    from services.tax import quarterly_gst_summary
    db = _db()
    try:
        quarterly_gst_summary(db)
        logger.info("Quarterly GST summary sent")
    except Exception as exc:
        logger.error("GST summary job failed: %s", exc)
    finally:
        db.close()


def job_t4a_reminder():
    from services.tax import t4a_reminder
    db = _db()
    try:
        t4a_reminder(db)
        logger.info("T4A reminder sent")
    except Exception as exc:
        logger.error("T4A reminder job failed: %s", exc)
    finally:
        db.close()


def job_qb_trip_sync():
    """Sync any un-synced completed trips to QuickBooks."""
    from models.trip import Trip, TripStatus
    import services.quickbooks as qb_service

    db = _db()
    try:
        unsynced = (
            db.query(Trip)
            .filter(Trip.status == TripStatus.COMPLETED, Trip.qb_synced == False)
            .limit(100)
            .all()
        )
        for trip in unsynced:
            try:
                qb_id = qb_service.push_trip_income(
                    db,
                    trip_id=trip.id,
                    fare=trip.fare,
                    gst=trip.gst_amount,
                    tip=trip.tip,
                    payment_method=trip.payment_method or "unknown",
                    trip_date=trip.completed_at,
                    driver_name=trip.driver.full_name if trip.driver else "Unknown",
                    city=trip.city,
                )
                trip.qb_income_id = qb_id
                trip.qb_synced = True
                db.commit()
            except Exception as exc:
                logger.error("QB sync failed for trip %s: %s", trip.id, exc)
        logger.info("QB trip sync: %d trips synced", len(unsynced))
    except Exception as exc:
        logger.error("QB trip sync job failed: %s", exc)
    finally:
        db.close()


# ─── Register Jobs ────────────────────────────────────────────────────────────

def start_scheduler():
    # Daily revenue summary — every night at 11:30 PM SKT
    scheduler.add_job(job_daily_revenue, CronTrigger(hour=23, minute=30), id="daily_revenue", replace_existing=True)

    # Weekly payroll — every Friday at 11:00 PM SKT
    scheduler.add_job(job_weekly_payroll, CronTrigger(day_of_week="fri", hour=23, minute=0), id="weekly_payroll", replace_existing=True)

    # Weekly P&L email — every Monday at 7:00 AM SKT
    scheduler.add_job(job_weekly_pnl, CronTrigger(day_of_week="mon", hour=7, minute=0), id="weekly_pnl", replace_existing=True)

    # Monthly invoices — 1st of each month at 6:00 AM
    scheduler.add_job(job_monthly_invoices, CronTrigger(day=1, hour=6, minute=0), id="monthly_invoices", replace_existing=True)

    # Monthly revenue report — 1st of each month at 6:30 AM
    scheduler.add_job(job_monthly_report, CronTrigger(day=1, hour=6, minute=30), id="monthly_report", replace_existing=True)

    # Invoice payment reminders — every day at 9:00 AM
    scheduler.add_job(job_invoice_reminders, CronTrigger(hour=9, minute=0), id="invoice_reminders", replace_existing=True)

    # Quarterly GST — 1st of April, July, October, January at 6:00 AM
    scheduler.add_job(job_quarterly_gst, CronTrigger(month="1,4,7,10", day=1, hour=6, minute=0), id="quarterly_gst", replace_existing=True)

    # T4A reminder — February 1st at 8:00 AM
    scheduler.add_job(job_t4a_reminder, CronTrigger(month=2, day=1, hour=8, minute=0), id="t4a_reminder", replace_existing=True)

    # QB trip sync — every 15 minutes
    scheduler.add_job(job_qb_trip_sync, CronTrigger(minute="*/15"), id="qb_trip_sync", replace_existing=True)

    scheduler.start()
    logger.info("Accounts agent scheduler started with %d jobs", len(scheduler.get_jobs()))
