"""
Daily compliance sweep — scans all documents, updates statuses,
triggers alerts, and auto-suspends drivers with expired docs.
"""
import logging
from datetime import date, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Document, DocumentStatus, Driver, DriverStatus
from compliance.database import AsyncSessionLocal
from compliance.services.alerts import send_expiry_alert, send_owner_alert
from compliance.services.suspension import suspend_driver_for_expired_docs

logger = logging.getLogger(__name__)

# Days-before-expiry thresholds for alerts
ALERT_THRESHOLDS = [60, 30, 14]

# Document types required per driver (city-specific handled in suspension)
REQUIRED_DRIVER_DOCS = [
    "drivers_abstract",
    "criminal_record_check",
    "taxi_license",
]

REQUIRED_VEHICLE_DOCS = [
    "sgi_insurance",
    "vehicle_registration",
    "safety_inspection",
]


async def run_daily_sweep():
    """Main compliance sweep — runs every morning at 6am."""
    logger.info("Starting daily compliance sweep...")
    async with AsyncSessionLocal() as db:
        today = date.today()
        stats = {
            "total_docs": 0,
            "valid": 0,
            "expiring_soon": 0,
            "expired": 0,
            "missing": 0,
            "drivers_suspended": 0,
        }

        result = await db.execute(select(Document))
        documents = result.scalars().all()
        stats["total_docs"] = len(documents)

        for doc in documents:
            old_status = doc.status
            new_status = _compute_status(doc.expiry_date, today)

            if new_status != old_status:
                await db.execute(
                    update(Document)
                    .where(Document.id == doc.id)
                    .values(status=new_status)
                )
                logger.info(f"Doc {doc.id} ({doc.doc_type}): {old_status} → {new_status}")

            stats[new_status.replace("_soon", "").replace("expiring", "expiring_soon")] = \
                stats.get(new_status, 0) + 1

            # Send threshold alerts
            if doc.expiry_date and new_status in (
                DocumentStatus.EXPIRING_SOON, DocumentStatus.VALID
            ):
                days_left = (doc.expiry_date - today).days
                if days_left in ALERT_THRESHOLDS:
                    await send_expiry_alert(db, doc, days_left)

            # Immediate alert on expiry
            if new_status == DocumentStatus.EXPIRED and old_status != DocumentStatus.EXPIRED:
                await send_owner_alert(
                    db,
                    subject=f"EXPIRED: {doc.doc_type} for entity {doc.entity_id}",
                    body=(
                        f"Document expired today: {doc.doc_type}\n"
                        f"Entity: {doc.entity_type} {doc.entity_id}\n"
                        f"Expiry date: {doc.expiry_date}"
                    ),
                )

        await db.commit()

        # Auto-suspend drivers with expired mandatory docs
        suspended = await _check_and_suspend_drivers(db)
        stats["drivers_suspended"] = suspended

        logger.info(f"Compliance sweep complete: {stats}")
        return stats


def _compute_status(expiry_date, today: date) -> str:
    if expiry_date is None:
        return DocumentStatus.MISSING
    if expiry_date < today:
        return DocumentStatus.EXPIRED
    if expiry_date <= today + timedelta(days=30):
        return DocumentStatus.EXPIRING_SOON
    return DocumentStatus.VALID


async def _check_and_suspend_drivers(db: AsyncSession) -> int:
    """Suspend any active driver who has an expired mandatory document."""
    suspended_count = 0
    today = date.today()

    result = await db.execute(
        select(Driver).where(Driver.status == DriverStatus.ACTIVE)
    )
    active_drivers = result.scalars().all()

    for driver in active_drivers:
        expired = await db.execute(
            select(Document).where(
                Document.entity_id == driver.id,
                Document.entity_type == "driver",
                Document.doc_type.in_(REQUIRED_DRIVER_DOCS),
                Document.status == DocumentStatus.EXPIRED,
            )
        )
        expired_docs = expired.scalars().all()

        if expired_docs:
            await suspend_driver_for_expired_docs(db, driver, expired_docs)
            suspended_count += 1

    await db.commit()
    return suspended_count
