"""Dispatch module: iCabbi-parity fields + new statuses

Brings the schema in line with the SQLAlchemy models after the
session-5 dispatch rebuild:

  Trips:
    + customer_email, via_address, instructions, site, priority
    + booking_source (enum)
    + noshow_at, scheduled_for
    + tripstatus enum value 'noshow'

  Drivers:
    + driverstatus enum values 'parked', 'dropping', 'bidding'

Idempotent where possible — uses IF NOT EXISTS guards so the migration
is safe to run on a database that was bootstrapped via
`Base.metadata.create_all` rather than Alembic.

Revision ID: 002
Revises: 001
Create Date: 2026-05-18
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # ── Extend tripstatus enum ──────────────────────────────────────────
    bind.exec_driver_sql("ALTER TYPE tripstatus ADD VALUE IF NOT EXISTS 'noshow'")

    # ── Extend driverstatus enum ────────────────────────────────────────
    for value in ("parked", "dropping", "bidding"):
        bind.exec_driver_sql(f"ALTER TYPE driverstatus ADD VALUE IF NOT EXISTS '{value}'")

    # ── Create bookingsource enum if missing ────────────────────────────
    bind.exec_driver_sql(
        """
        DO $$ BEGIN
            CREATE TYPE bookingsource AS ENUM ('phone', 'app', 'web', 'whatsapp', 'agent');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    # ── Add columns to trips (each guarded with IF NOT EXISTS) ──────────
    bind.exec_driver_sql(
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS customer_email VARCHAR(200) NOT NULL DEFAULT ''"
    )
    bind.exec_driver_sql(
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS via_address VARCHAR(300) NOT NULL DEFAULT ''"
    )
    bind.exec_driver_sql(
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS instructions TEXT NOT NULL DEFAULT ''"
    )
    bind.exec_driver_sql(
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS site VARCHAR(80) NOT NULL DEFAULT ''"
    )
    bind.exec_driver_sql(
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS priority INTEGER NOT NULL DEFAULT 0"
    )
    bind.exec_driver_sql(
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS noshow_at TIMESTAMPTZ NULL"
    )
    bind.exec_driver_sql(
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS scheduled_for TIMESTAMPTZ NULL"
    )
    bind.exec_driver_sql(
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS booking_source bookingsource NOT NULL DEFAULT 'agent'"
    )

    # Helpful index for the queue endpoint
    bind.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_trips_status_created ON trips (status, created_at)"
    )
    bind.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_trips_scheduled_for ON trips (scheduled_for)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql("DROP INDEX IF EXISTS ix_trips_scheduled_for")
    bind.exec_driver_sql("DROP INDEX IF EXISTS ix_trips_status_created")
    for col in (
        "booking_source",
        "scheduled_for",
        "noshow_at",
        "priority",
        "site",
        "instructions",
        "via_address",
        "customer_email",
    ):
        bind.exec_driver_sql(f"ALTER TABLE trips DROP COLUMN IF EXISTS {col}")
    # Note: PostgreSQL cannot remove individual enum values without recreating
    # the type. The added tripstatus/driverstatus values and bookingsource type
    # are left in place on downgrade.
