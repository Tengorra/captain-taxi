"""
Generates compliance health reports for the owner.
"""
import logging
from datetime import date
from sqlalchemy import select, func
from core.models import Document, DocumentStatus, Driver, DriverStatus
from compliance.database import AsyncSessionLocal
from compliance.services.alerts import send_owner_alert

logger = logging.getLogger(__name__)


async def generate_weekly_report():
    async with AsyncSessionLocal() as db:
        today = date.today()

        # Count docs by status
        result = await db.execute(
            select(Document.status, func.count(Document.id))
            .group_by(Document.status)
        )
        status_counts = {row[0]: row[1] for row in result.all()}

        # Count active/suspended drivers
        driver_result = await db.execute(
            select(Driver.status, func.count(Driver.id))
            .group_by(Driver.status)
        )
        driver_counts = {row[0]: row[1] for row in driver_result.all()}

        valid = status_counts.get(DocumentStatus.VALID, 0)
        expiring = status_counts.get(DocumentStatus.EXPIRING_SOON, 0)
        expired = status_counts.get(DocumentStatus.EXPIRED, 0)
        missing = status_counts.get(DocumentStatus.MISSING, 0)

        active_drivers = driver_counts.get(DriverStatus.ACTIVE, 0)
        suspended_drivers = driver_counts.get(DriverStatus.SUSPENDED, 0)

        report = (
            f"Weekly Compliance Report — {today}\n"
            f"Documents: {valid} valid | {expiring} expiring soon | "
            f"{expired} expired | {missing} missing\n"
            f"Drivers: {active_drivers} active | {suspended_drivers} suspended"
        )

        await send_owner_alert(db, subject="Weekly Compliance Report", body=report)
        logger.info("Weekly compliance report sent.")
        return report


async def get_compliance_summary(db) -> dict:
    """Returns a compliance summary dict for the dashboard."""
    result = await db.execute(
        select(Document.status, func.count(Document.id)).group_by(Document.status)
    )
    status_counts = {row[0]: row[1] for row in result.all()}

    return {
        "valid": status_counts.get(DocumentStatus.VALID, 0),
        "expiring_soon": status_counts.get(DocumentStatus.EXPIRING_SOON, 0),
        "expired": status_counts.get(DocumentStatus.EXPIRED, 0),
        "missing": status_counts.get(DocumentStatus.MISSING, 0),
        "as_of": date.today().isoformat(),
    }
