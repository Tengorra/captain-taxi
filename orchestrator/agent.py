"""
Orchestrator Agent — Claude-powered event router for Captain Taxi.

Receives every event published to captain.events, uses Claude to decide
which sub-agent should handle it, then publishes the task to that agent's
channel. Also detects escalation triggers and notifies owner when needed.
"""
import json
import time
from datetime import datetime

import anthropic
import structlog

from core.config import get_settings
from core.redis_client import publish
from orchestrator.escalation import escalate_to_owner, should_escalate

log = structlog.get_logger()
settings = get_settings()

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

# ── Agent channel mapping ──────────────────────────────────────────────────────
AGENT_CHANNELS = {
    "dispatch": "dispatch",
    "customer": "customer",
    "drivers": "drivers",
    "accounts": "accounts",
    "compliance": "compliance",
    "admin": "admin",
}

SYSTEM_PROMPT = """You are the Orchestrator for Captain Taxi, a taxi company in Saskatoon and Regina, Saskatchewan, Canada.

Your job is to analyze incoming events and decide which specialist agent should handle each one, or whether the owner must be notified.

Available agents:
- dispatch: Trip booking, ride assignment, driver availability, iCabbi/Autocab dispatch
- customer: Customer service, complaints, lost & found, reviews, WhatsApp/SMS/phone support
- drivers: Driver onboarding, scheduling, performance, pay disputes, HR matters
- accounts: Invoicing, driver payouts, expenses, QuickBooks, financial reporting
- compliance: Driver document renewals (SGI insurance, taxi license, criminal checks, vehicle inspections)
- admin: Internal communications, staff scheduling, office operations, general admin tasks

Escalation rules — ONLY escalate to owner for:
1. Driver termination or firing
2. Expenses or payments over $500 that aren't routine payroll
3. Legal threats, lawsuits, police involvement, criminal matters
4. New contracts or partnership agreements
5. Anything that could seriously harm the company

For everything else, route to the appropriate agent and let them handle it autonomously.

You must respond with valid JSON only, in this exact format:
{
  "target_agent": "<agent_name or 'escalate'>",
  "task": "<clear instruction for the target agent>",
  "priority": "<low|medium|high|critical>",
  "escalate": <true|false>,
  "escalation_reason": "<reason if escalate=true, else null>",
  "notify_amara": <true|false>,
  "reasoning": "<one sentence explaining your decision>"
}"""


async def route_event(event: dict) -> dict:
    """
    Takes an event dict from any agent, asks Claude to route it,
    publishes the task to the right channel, and handles escalation.

    Returns the routing decision.
    """
    start = time.perf_counter()
    event_str = json.dumps(event, indent=2, default=str)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"Route this event:\n\n{event_str}",
                }
            ],
        )

        raw = response.content[0].text.strip()
        # Strip markdown fences if Claude wraps in ```json
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        decision = json.loads(raw.strip())

    except json.JSONDecodeError as exc:
        log.error("route_json_parse_error", error=str(exc), raw=raw)
        decision = _fallback_decision(event)
    except Exception as exc:
        log.error("route_claude_error", error=str(exc))
        decision = _fallback_decision(event)

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    log.info(
        "event_routed",
        target=decision.get("target_agent"),
        priority=decision.get("priority"),
        escalate=decision.get("escalate"),
        duration_ms=elapsed_ms,
    )

    # ── Escalate if needed ─────────────────────────────────────────────────────
    if decision.get("escalate") or should_escalate(event_str):
        _handle_escalation(event, decision)

    # ── Publish task to target agent ───────────────────────────────────────────
    target = decision.get("target_agent", "admin")
    if target in AGENT_CHANNELS:
        await publish(AGENT_CHANNELS[target], {
            "task": decision.get("task", ""),
            "priority": decision.get("priority", "medium"),
            "source_event": event,
            "routing_decision": decision,
            "routed_at": datetime.utcnow().isoformat(),
        })

    return decision


def _handle_escalation(event: dict, decision: dict) -> None:
    reason = decision.get("escalation_reason") or "Automated escalation triggered"
    details = (
        f"Event type: {event.get('event_type', 'unknown')}\n"
        f"Agent task: {decision.get('task', '')}\n"
        f"Event source: {event.get('source_agent', 'unknown')}\n\n"
        f"Full event:\n{json.dumps(event, indent=2, default=str)[:800]}"
    )
    priority = decision.get("priority", "high")
    notify_amara = decision.get("notify_amara", False) or priority == "critical"

    result = escalate_to_owner(
        agent=event.get("source_agent", "unknown"),
        reason=reason,
        details=details,
        priority=priority,
        also_notify_amara=notify_amara,
    )
    log.info("escalation_sent", notified=result.notified, whatsapp=result.whatsapp_sent)


def _fallback_decision(event: dict) -> dict:
    """Safe fallback when Claude is unavailable — route to admin."""
    return {
        "target_agent": "admin",
        "task": f"Manual review needed: {json.dumps(event, default=str)[:300]}",
        "priority": "medium",
        "escalate": False,
        "escalation_reason": None,
        "notify_amara": False,
        "reasoning": "Fallback — Claude routing unavailable",
    }
