"""
Escalation rules for Captain Taxi Orchestrator.

Owner is ONLY contacted for:
  1. Driver termination
  2. Expenses > $500
  3. Legal issues / lawsuits / police
  4. New contracts / partnership agreements
  5. Any issue flagged critical that agents cannot resolve

All other decisions are handled autonomously.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime

import structlog
from twilio.rest import Client

from core.config import get_settings
from core.utils import whatsapp_number

log = structlog.get_logger()
settings = get_settings()

# ── Hardcoded contacts ─────────────────────────────────────────────────────────
OWNER_PHONE = "+13068811542"
AMARA_PHONE = "+13068500760"

# ── Escalation trigger patterns ────────────────────────────────────────────────
ESCALATION_KEYWORDS = [
    r"terminat",
    r"fire\b",
    r"fired\b",
    r"lawsuit",
    r"legal\s+action",
    r"police",
    r"\blawyer\b",
    r"court\b",
    r"contract\b.*sign",
    r"new\s+contract",
    r"partnership",
    r"expense.*[5-9]\d{2,}",      # $500+
    r"\$[5-9]\d{2,}",
    r"criminal",
    r"assault",
    r"accident.*serious",
]

ESCALATION_PATTERN = re.compile(
    "|".join(ESCALATION_KEYWORDS), re.IGNORECASE
)


@dataclass
class EscalationResult:
    should_escalate: bool
    reason: str = ""
    notified: list[str] = field(default_factory=list)
    whatsapp_sent: bool = False


def should_escalate(text: str, amount: float | None = None) -> bool:
    """Quick check — does this text/amount require owner involvement?"""
    if amount and amount > 500:
        return True
    return bool(ESCALATION_PATTERN.search(text))


def _send_whatsapp(to: str, body: str) -> bool:
    """Send a WhatsApp message via Twilio. Returns True on success."""
    try:
        if not settings.twilio_account_sid or not settings.twilio_auth_token:
            log.warning("twilio_not_configured", to=to)
            return False

        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        client.messages.create(
            from_=settings.twilio_whatsapp_from,
            to=whatsapp_number(to),
            body=body,
        )
        log.info("whatsapp_sent", to=to)
        return True
    except Exception as exc:
        log.error("whatsapp_send_failed", to=to, error=str(exc))
        return False


def escalate_to_owner(
    agent: str,
    reason: str,
    details: str,
    priority: str = "high",
    also_notify_amara: bool = False,
) -> EscalationResult:
    """
    Send WhatsApp alert to owner. Optionally cc Amara.
    Always logs to DB via caller (orchestrator saves the Escalation record).
    """
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    icon = "🚨" if priority == "critical" else "⚠️"

    message = (
        f"{icon} *Captain Taxi — Action Required*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"*From:* {agent}\n"
        f"*Priority:* {priority.upper()}\n"
        f"*Reason:* {reason}\n\n"
        f"{details}\n\n"
        f"_Reply to this message to respond._\n"
        f"_{timestamp}_"
    )

    notified: list[str] = []
    owner_ok = _send_whatsapp(OWNER_PHONE, message)
    if owner_ok:
        notified.append("owner")

    amara_ok = False
    if also_notify_amara or priority == "critical":
        amara_ok = _send_whatsapp(AMARA_PHONE, message)
        if amara_ok:
            notified.append("amara")

    return EscalationResult(
        should_escalate=True,
        reason=reason,
        notified=notified,
        whatsapp_sent=owner_ok or amara_ok,
    )
