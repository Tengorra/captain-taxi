"""
Warm-transfer an in-flight call to a human dispatcher line.

ElevenLabs hands us the underlying Twilio CallSid; we use Twilio's REST API
to replace the call's TwiML with a <Dial> to the human number, which causes
the live caller to be bridged to the human while the bot drops off.
"""
from __future__ import annotations

import logging
from typing import Literal

from twilio.rest import Client

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _client() -> Client:
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


def human_number_for(city: Literal["saskatoon", "regina"] | str) -> str:
    return (
        settings.human_dispatcher_regina
        if (city or "").lower() == "regina"
        else settings.human_dispatcher_saskatoon
    )


async def transfer_call(
    twilio_call_sid: str,
    city: str = "saskatoon",
    reason: str = "bot escalation",
) -> dict:
    """Redirect the live Twilio call to a human dispatcher number."""
    if not (settings.twilio_account_sid and settings.twilio_auth_token):
        logger.warning("Twilio not configured — cannot transfer call %s", twilio_call_sid)
        return {"status": "skipped", "reason": "twilio not configured"}

    target = human_number_for(city)
    twiml = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<Response>'
        f'<Say voice="alice">One moment, transferring you to a dispatcher.</Say>'
        f'<Dial callerId="{settings.twilio_phone_from}">{target}</Dial>'
        f'</Response>'
    )
    try:
        _client().calls(twilio_call_sid).update(twiml=twiml)
    except Exception as e:
        logger.exception("Failed to transfer Twilio call %s", twilio_call_sid)
        return {"status": "error", "error": str(e)}

    logger.info("Transferred call %s → %s (%s)", twilio_call_sid, target, reason)
    return {"status": "transferred", "to": target, "reason": reason}
