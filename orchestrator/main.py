"""
Orchestrator FastAPI application.

Endpoints:
  POST /events          — any agent publishes an event here
  GET  /health          — health check
  GET  /escalations     — list open escalations
  POST /escalations/{id}/resolve — mark escalation resolved
  GET  /logs            — recent agent logs
  GET  /digest/preview  — preview today's digest without sending
"""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.database import get_db, AsyncSessionLocal
from core.models import AgentLog, Escalation, EscalationStatus
from core.redis_client import subscribe_forever, publish
from core.utils import configure_logging
from orchestrator.agent import route_event
from orchestrator.digest import send_daily_digest, build_digest

settings = get_settings()
configure_logging(settings.log_level)
log = structlog.get_logger()

scheduler = AsyncIOScheduler(timezone="America/Regina")


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("orchestrator_starting")

    # Start Redis event listener in background
    asyncio.create_task(
        subscribe_forever("events", _handle_redis_event),
        name="redis_listener",
    )

    # Daily digest at 8am Saskatchewan time (UTC-6, no DST)
    scheduler.add_job(
        _run_daily_digest,
        "cron",
        hour=settings.digest_hour,
        minute=settings.digest_minute,
        id="daily_digest",
    )
    scheduler.start()

    log.info("orchestrator_ready")
    yield

    scheduler.shutdown()
    log.info("orchestrator_stopped")


async def _handle_redis_event(event: dict) -> None:
    """Called for every message on captain.events channel."""
    async with AsyncSessionLocal() as db:
        try:
            decision = await route_event(event)
            log_entry = AgentLog(
                agent_name="orchestrator",
                action=f"route:{event.get('event_type', 'unknown')}",
                result=str(decision.get("target_agent")),
                metadata=decision,
                success=True,
            )
            db.add(log_entry)
            await db.commit()
        except Exception as exc:
            log.error("event_handling_failed", error=str(exc))
            await db.rollback()


async def _run_daily_digest() -> None:
    async with AsyncSessionLocal() as db:
        await send_daily_digest(db)


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Captain Taxi — Orchestrator",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Schemas ────────────────────────────────────────────────────────────────────

class EventPayload(BaseModel):
    event_type: str
    source_agent: str
    data: dict
    priority: str = "medium"


class ResolveEscalationRequest(BaseModel):
    response: str | None = None


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "orchestrator", "time": datetime.utcnow().isoformat()}


@app.post("/events")
async def receive_event(payload: EventPayload, db: AsyncSession = Depends(get_db)):
    """
    Any agent POSTs an event here. Orchestrator routes it via Claude
    and publishes to the appropriate agent channel.
    """
    event = payload.model_dump()
    decision = await route_event(event)

    log_entry = AgentLog(
        agent_name="orchestrator",
        action=f"route_http:{payload.event_type}",
        result=decision.get("target_agent"),
        metadata=decision,
        success=True,
    )
    db.add(log_entry)

    return {"status": "routed", "decision": decision}


@app.get("/escalations")
async def list_escalations(
    status: str = "open",
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Escalation)
        .where(Escalation.status == status)
        .order_by(Escalation.created_at.desc())
        .limit(limit)
    )
    escalations = result.scalars().all()
    return [
        {
            "id": e.id,
            "agent": e.agent,
            "reason": e.reason,
            "priority": e.priority,
            "status": e.status,
            "notified_owner": e.notified_owner,
            "created_at": e.created_at.isoformat(),
        }
        for e in escalations
    ]


@app.post("/escalations/{escalation_id}/resolve")
async def resolve_escalation(
    escalation_id: int,
    body: ResolveEscalationRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Escalation).where(Escalation.id == escalation_id)
    )
    esc = result.scalar_one_or_none()
    if not esc:
        raise HTTPException(status_code=404, detail="Escalation not found")

    esc.status = EscalationStatus.RESOLVED
    esc.resolved_at = datetime.utcnow()
    if body.response:
        esc.owner_response = body.response

    return {"status": "resolved", "id": escalation_id}


@app.get("/logs")
async def get_logs(
    agent: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    q = select(AgentLog).order_by(AgentLog.timestamp.desc()).limit(limit)
    if agent:
        q = q.where(AgentLog.agent_name == agent)
    result = await db.execute(q)
    logs = result.scalars().all()
    return [
        {
            "id": l.id,
            "agent": l.agent_name,
            "action": l.action,
            "result": l.result,
            "success": l.success,
            "timestamp": l.timestamp.isoformat(),
        }
        for l in logs
    ]


@app.get("/digest/preview")
async def preview_digest(db: AsyncSession = Depends(get_db)):
    """Generate the daily digest without sending it — for testing."""
    message = await build_digest(db)
    return {"digest": message}


@app.post("/digest/send")
async def send_digest_now(db: AsyncSession = Depends(get_db)):
    """Manually trigger the daily digest."""
    await send_daily_digest(db)
    return {"status": "sent"}
