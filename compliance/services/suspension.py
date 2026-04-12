"""
Auto-suspends drivers when mandatory compliance documents expire.
"""
import logging
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from twilio.rest import Client

from core.models import Driver, DriverStatus, Document
from core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def suspend_driver_for_expired_docs(
    db: AsyncSession, driver: Driver, expired_docs: list[Document]
):
    doc_names = ", ".join(d.doc_type for d in expired_docs)
    logger.warning(f"Auto-suspending driver {driver.name} — expired: {doc_names}")

    await db.execute(
        update(Driver)
        .where(Driver.id == driver.id)
        .values(status=DriverStatus.SUSPENDED)
    )

    # Notify driver
    if driver.phone:
        _send_sms(
            driver.phone,
            f"[Captain Taxi] Your account has been suspended due to expired compliance "
            f"documents: {doc_names}. Please contact management to reactivate."
        )

    # Notify owner
    _send_sms(
        settings.owner_phone,
        f"[Captain Taxi Compliance] Driver {driver.name} ({driver.phone}) auto-suspended. "
        f"Expired docs: {doc_names}."
    )


async def reinstate_driver(db: AsyncSession, driver_id: str) -> bool:
    """Reinstate a suspended driver after all docs are verified valid."""
    await db.execute(
        update(Driver)
        .where(Driver.id == driver_id)
        .values(status=DriverStatus.ACTIVE)
    )
    await db.commit()
    logger.info(f"Driver {driver_id} reinstated.")
    return True


def _send_sms(to: str, body: str):
    if not settings.twilio_account_sid:
        logger.warning(f"Twilio not configured. Would send to {to}: {body}")
        return
    try:
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        client.messages.create(
            body=body,
            from_=settings.twilio_whatsapp_from.replace("whatsapp:", ""),
            to=to,
        )
    except Exception as e:
        logger.error(f"SMS failed to {to}: {e}")
