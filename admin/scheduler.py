"""
APScheduler setup for daily digest and weekly report.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

TIMEZONE = pytz.timezone("America/Regina")  # Saskatchewan (no DST)
scheduler = AsyncIOScheduler(timezone=TIMEZONE)


def setup_scheduler():
    # Daily digest at 7:00 AM (Saskatchewan time)
    scheduler.add_job(
        _run_daily_digest,
        CronTrigger(hour=7, minute=0, timezone=TIMEZONE),
        id="daily_digest",
        replace_existing=True,
        name="Daily WhatsApp Digest",
    )

    # Weekly report every Monday at 7:30 AM
    scheduler.add_job(
        _run_weekly_report,
        CronTrigger(day_of_week="mon", hour=7, minute=30, timezone=TIMEZONE),
        id="weekly_report",
        replace_existing=True,
        name="Weekly Email Report",
    )

    # Expire old escalations every hour
    scheduler.add_job(
        _expire_escalations,
        CronTrigger(minute=0),
        id="expire_escalations",
        replace_existing=True,
        name="Expire Old Escalations",
    )

    # Monthly owner-statement roll-up — 1st of each month at 4 AM
    scheduler.add_job(
        _run_monthly_owner_statements,
        CronTrigger(day=1, hour=4, minute=0, timezone=TIMEZONE),
        id="monthly_owner_statements",
        replace_existing=True,
        name="Monthly Owner Statement Generation",
    )

    # Nightly iCabbi sync — 3 AM. No-op when ICABBI_* env vars aren't set.
    scheduler.add_job(
        _run_icabbi_sync,
        CronTrigger(hour=3, minute=0, timezone=TIMEZONE),
        id="icabbi_nightly_sync",
        replace_existing=True,
        name="Nightly iCabbi Sync",
    )

    scheduler.start()
    print("[Scheduler] Jobs scheduled: daily digest 7am, weekly report Mondays 7:30am, "
          "monthly owner statements 1st @ 4am, nightly iCabbi sync 3am")


async def _run_daily_digest():
    from .agents.digest import send_daily_digest
    send_daily_digest()


async def _run_weekly_report():
    from .agents.digest import send_weekly_email_report
    send_weekly_email_report()


async def _run_monthly_owner_statements():
    from .services.owner_statements_service import generate_for_last_month
    try:
        result = generate_for_last_month()
        print(f"[Scheduler] Owner statements: created={result['created_count']} "
              f"skipped={result['skipped_count']} for {result['period_start']}→{result['period_end']}")
    except Exception as e:
        print(f"[Scheduler] Owner statement run failed: {e}")


async def _run_icabbi_sync():
    from .services.icabbi_client import IcabbiClient
    if not IcabbiClient.is_configured():
        # Silent skip — owner hasn't set ICABBI_BASE_URL / ICABBI_API_KEY yet.
        return
    from .services.icabbi_sync import sync_all
    try:
        result = await sync_all()
        counts = ", ".join(
            f"{name}: +{r.get('created', 0)}/~{r.get('updated', 0)}"
            for name, r in result.get("results", {}).items()
        )
        print(f"[Scheduler] iCabbi sync — {counts}")
    except Exception as e:
        print(f"[Scheduler] iCabbi sync failed: {e}")


async def _expire_escalations():
    """Mark long-unresolved escalations as expired so they stop pinging the
    owner. Uses the `escalation_timeout_hours` Settings row (default 4h).
    Schema note: Escalation.status is a free-form String — values used are
    'open' / 'resolved' / 'expired'. The model has no `expires_at` column;
    we compute expiry from created_at + the configured timeout."""
    from .db.database import SessionLocal
    from .db.models import Escalation, Settings
    from datetime import datetime, timedelta, timezone
    db = SessionLocal()
    try:
        row = db.query(Settings).filter_by(key="escalation_timeout_hours").first()
        try:
            hours = int(row.value) if row else 4
        except (TypeError, ValueError):
            hours = 4
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        expired = db.query(Escalation).filter(
            Escalation.status == "open",
            Escalation.created_at < cutoff,
        ).all()
        for e in expired:
            e.status = "expired"
        if expired:
            db.commit()
            print(f"[Scheduler] Expired {len(expired)} escalation(s) older than {hours}h")
    finally:
        db.close()
