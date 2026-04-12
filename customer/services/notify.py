"""
Outbound notifications:
- SMS confirmation to customer (Twilio)
- Owner alert (Twilio SMS) for serious escalations
"""

from twilio.rest import Client
from config import get_settings

settings = get_settings()

_client: Client | None = None


def _twilio() -> Client:
    global _client
    if _client is None:
        _client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    return _client


def _from_number(to: str) -> str:
    """Pick the appropriate Captain Taxi number based on context (default Saskatoon)."""
    return settings.twilio_sms_from_saskatoon


def send_booking_confirmation(
    to_phone: str,
    trip_id: str,
    pickup: str,
    dropoff: str,
    channel: str = "sms",
) -> None:
    body = (
        f"Captain Taxi booking confirmed!\n"
        f"Trip ID: {trip_id}\n"
        f"From: {pickup}\n"
        f"To: {dropoff}\n"
        f"Reply CANCEL {trip_id} to cancel.\n"
        f"Questions? Reply here or call 306-242-0000."
    )
    if channel == "whatsapp":
        _twilio().messages.create(
            from_=settings.twilio_whatsapp_from,
            to=f"whatsapp:{to_phone}",
            body=body,
        )
    else:
        _twilio().messages.create(
            from_=_from_number(to_phone),
            to=to_phone,
            body=body,
        )


def send_discount(to_phone: str, code: str, channel: str = "sms") -> None:
    body = (
        f"We're sorry about your experience with Captain Taxi.\n"
        f"As an apology, use code {code} for $5 off your next ride.\n"
        f"Call us at 306-242-0000 with any questions."
    )
    if channel == "whatsapp":
        _twilio().messages.create(
            from_=settings.twilio_whatsapp_from,
            to=f"whatsapp:{to_phone}",
            body=body,
        )
    else:
        _twilio().messages.create(
            from_=_from_number(to_phone),
            to=to_phone,
            body=body,
        )


def alert_owner_escalation(
    customer_phone: str,
    complaint_description: str,
    trip_id: str | None = None,
    channel: str = "unknown",
) -> None:
    body = (
        f"🚨 CAPTAIN TAXI — SERIOUS COMPLAINT\n"
        f"Channel: {channel}\n"
        f"Customer: {customer_phone}\n"
        f"Trip: {trip_id or 'unknown'}\n"
        f"Details: {complaint_description[:200]}\n"
        f"Action required immediately."
    )
    _twilio().messages.create(
        from_=settings.twilio_sms_from_saskatoon,
        to=settings.owner_phone,
        body=body,
    )
