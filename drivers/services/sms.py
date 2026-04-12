"""Twilio SMS service — send and receive SMS to/from drivers."""
import logging
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from config import settings

logger = logging.getLogger(__name__)

_client: Client | None = None


def get_twilio() -> Client:
    global _client
    if _client is None:
        _client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    return _client


async def send_sms(to: str, body: str) -> str | None:
    """
    Send an SMS to a phone number (E.164 format).
    Returns Twilio message SID or None on failure.
    """
    try:
        client = get_twilio()
        msg = client.messages.create(
            body=body,
            from_=settings.twilio_phone_number,
            to=to,
        )
        logger.info(f"SMS sent to {to}: SID={msg.sid}")
        return msg.sid
    except TwilioRestException as e:
        logger.error(f"Twilio error sending to {to}: {e}")
        return None


async def send_sms_bulk(recipients: list[dict]) -> list[dict]:
    """
    Send SMS to multiple recipients.
    recipients: [{"phone": "+1...", "body": "..."}]
    Returns list of {"phone", "sid", "success"}.
    """
    results = []
    for r in recipients:
        sid = await send_sms(r["phone"], r["body"])
        results.append({"phone": r["phone"], "sid": sid, "success": sid is not None})
    return results
