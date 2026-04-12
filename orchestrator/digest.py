"""
Daily 8am digest — summarizes past 24h for the owner via WhatsApp.
"""
from datetime import datetime, timedelta

import anthropic
import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.models import AgentLog, Trip, Escalation, Driver, TripStatus, EscalationStatus
from orchestrator.escalation import _send_whatsapp, OWNER_PHONE, AMARA_PHONE

log = structlog.get_logger()
settings = get_settings()
client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


async def build_digest(db: AsyncSession) -> str:
    """Query last 24h stats and ask Claude to write a concise WhatsApp summary."""
    since = datetime.utcnow() - timedelta(hours=24)

    # ── Raw stats ──────────────────────────────────────────────────────────────
    trips_completed = await db.scalar(
        select(func.count(Trip.id)).where(
            Trip.status == TripStatus.COMPLETED,
            Trip.completed_at >= since,
        )
    )
    trips_cancelled = await db.scalar(
        select(func.count(Trip.id)).where(
            Trip.status == TripStatus.CANCELLED,
            Trip.created_at >= since,
        )
    )
    revenue = await db.scalar(
        select(func.sum(Trip.fare)).where(
            Trip.status == TripStatus.COMPLETED,
            Trip.completed_at >= since,
        )
    ) or 0.0

    active_drivers = await db.scalar(
        select(func.count(Driver.id)).where(Driver.status == "active")
    )

    open_escalations = await db.scalar(
        select(func.count(Escalation.id)).where(
            Escalation.status == EscalationStatus.OPEN
        )
    )

    recent_logs = await db.execute(
        select(AgentLog)
        .where(AgentLog.timestamp >= since, AgentLog.success.is_(False))
        .order_by(AgentLog.timestamp.desc())
        .limit(5)
    )
    errors = recent_logs.scalars().all()
    error_summary = "\n".join(
        f"- [{e.agent_name}] {e.action}: {(e.result or '')[:100]}" for e in errors
    ) or "None"

    stats_text = f"""
24-hour stats for Captain Taxi:
- Completed trips: {trips_completed}
- Cancelled trips: {trips_cancelled}
- Revenue collected: ${revenue:.2f}
- Active drivers: {active_drivers}
- Open escalations awaiting owner: {open_escalations}
- Agent errors in last 24h: {error_summary}
"""

    # ── Ask Claude to write the digest ─────────────────────────────────────────
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        system=(
            "You are writing a short daily WhatsApp summary for the owner of Captain Taxi. "
            "Be concise, friendly, and highlight anything that needs attention. "
            "Use plain text with minimal formatting (WhatsApp style). "
            "Start with 'Good morning!' and end with a one-line status verdict."
        ),
        messages=[{"role": "user", "content": stats_text}],
    )

    return response.content[0].text.strip()


async def send_daily_digest(db: AsyncSession) -> None:
    log.info("digest_starting")
    try:
        message = await build_digest(db)
        sent = _send_whatsapp(OWNER_PHONE, message)
        log.info("digest_sent", to="owner", success=sent)
    except Exception as exc:
        log.error("digest_failed", error=str(exc))
