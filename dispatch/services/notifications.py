"""
SMS notifications via Twilio.

All notification functions are fire-and-forget coroutines — they log
failures but never raise, so a failed SMS never blocks dispatch.
"""

import logging
from typing import Optional
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _get_twilio_client():
    """Lazy-import Twilio so the service starts without the package if not configured."""
    try:
        from twilio.rest import Client
        return Client(settings.twilio_account_sid, settings.twilio_auth_token)
    except ImportError:
        logger.warning("twilio package not installed — SMS disabled")
        return None
    except Exception as exc:
        logger.error("Failed to init Twilio client: %s", exc)
        return None


async def send_sms(to: str, body: str) -> bool:
    """Send an SMS. Returns True on success."""
    if not settings.twilio_account_sid or not settings.twilio_from_number:
        logger.warning("Twilio not configured — skipping SMS to %s", to)
        return False
    client = _get_twilio_client()
    if not client:
        return False
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        msg = await loop.run_in_executor(
            None,
            lambda: client.messages.create(
                body=body,
                from_=settings.twilio_from_number,
                to=to,
            ),
        )
        logger.info("SMS sent sid=%s to=%s", msg.sid, to)
        return True
    except Exception as exc:
        logger.error("SMS failed to=%s: %s", to, exc)
        return False


async def notify_driver_trip_assigned(
    driver_phone: str,
    driver_name: str,
    trip_id: str,
    pickup_address: str,
    customer_name: str,
    customer_phone: str,
):
    body = (
        f"Hi {driver_name}, you have a new trip!\n"
        f"Pickup: {pickup_address}\n"
        f"Customer: {customer_name} ({customer_phone})\n"
        f"Trip ID: {trip_id[:8].upper()}\n"
        f"Please accept or decline in the app within 90 seconds."
    )
    await send_sms(driver_phone, body)


async def notify_customer_driver_en_route(
    customer_phone: str,
    customer_name: str,
    driver_name: str,
    vehicle_model: str,
    vehicle_plate: str,
    eta_minutes: Optional[int] = None,
):
    eta_str = f" (~{eta_minutes} min)" if eta_minutes else ""
    body = (
        f"Hi {customer_name or 'there'}! Your Captain Taxi is on the way{eta_str}.\n"
        f"Driver: {driver_name}\n"
        f"Vehicle: {vehicle_model} — {vehicle_plate}"
    )
    await send_sms(customer_phone, body)


async def notify_customer_trip_cancelled(
    customer_phone: str,
    customer_name: str,
    reason: str = "",
):
    body = (
        f"Hi {customer_name or 'there'}, unfortunately your Captain Taxi booking "
        f"has been cancelled. {reason}\n"
        f"Please call us or re-book. Sorry for the inconvenience."
    )
    await send_sms(customer_phone, body)
