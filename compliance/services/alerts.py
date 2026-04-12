"""
Sends compliance alerts to drivers (SMS) and owner (WhatsApp/SMS).
"""
import logging
from twilio.rest import Client

from core.config import get_settings
from core.models import Document, Driver
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)
settings = get_settings()

DOC_TYPE_LABELS = {
    "drivers_abstract": "Driver's Abstract",
    "criminal_record_check": "Criminal Record Check",
    "taxi_license": "Taxi License",
    "sgi_insurance": "SGI Vehicle Insurance",
    "vehicle_registration": "Vehicle Registration",
    "safety_inspection": "Vehicle Safety Inspection",
}


def _twilio_client():
    if settings.twilio_account_sid and settings.twilio_auth_token:
        return Client(settings.twilio_account_sid, settings.twilio_auth_token)
    return None


async def send_expiry_alert(db: AsyncSession, doc: Document, days_left: int):
    """Alert driver and owner about an upcoming document expiry."""
    doc_label = DOC_TYPE_LABELS.get(doc.doc_type, doc.doc_type)
    urgency = "URGENT" if days_left <= 14 else "Reminder"

    if doc.entity_type == "driver":
        result = await db.execute(select(Driver).where(Driver.id == doc.entity_id))
        driver = result.scalar_one_or_none()
        if driver and driver.phone:
            msg = (
                f"[Captain Taxi {urgency}] Hi {driver.name}, your {doc_label} "
                f"expires in {days_left} days ({doc.expiry_date}). "
                f"Please upload renewal to avoid suspension. Reply HELP for info."
            )
            _send_sms(driver.phone, msg)
            logger.info(f"Expiry alert sent to driver {driver.name} for {doc_label} ({days_left}d)")

    # Always alert owner at 14-day threshold
    if days_left <= 14:
        entity_info = f"{doc.entity_type} {doc.entity_id}"
        if doc.entity_type == "driver":
            result = await db.execute(select(Driver).where(Driver.id == doc.entity_id))
            d = result.scalar_one_or_none()
            if d:
                entity_info = f"Driver: {d.name} ({d.phone})"

        owner_msg = (
            f"[Captain Taxi Compliance] {urgency}: {entity_info} — "
            f"{doc_label} expires in {days_left} days ({doc.expiry_date})."
        )
        _send_sms(settings.owner_phone, owner_msg)


async def send_owner_alert(db: AsyncSession, subject: str, body: str):
    """Send a compliance alert directly to the owner."""
    msg = f"[Captain Taxi Compliance] {subject}\n{body}"
    _send_sms(settings.owner_phone, msg)
    logger.warning(f"Owner compliance alert sent: {subject}")


def _send_sms(to: str, body: str):
    client = _twilio_client()
    if not client:
        logger.warning(f"Twilio not configured. Would have sent to {to}: {body}")
        return
    try:
        client.messages.create(
            body=body,
            from_=settings.twilio_whatsapp_from.replace("whatsapp:", ""),
            to=to,
        )
    except Exception as e:
        logger.error(f"SMS send failed to {to}: {e}")
