"""Expand drivers table with full iCabbi field set; relax NOT NULL/UNIQUE on name/phone

Revision ID: 002
Revises: 001
Create Date: 2026-05-17
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Relax NOT NULL on name + phone, drop UNIQUE on phone — iCabbi exports
    # contain blank-phone and duplicate-phone rows (placeholder "_copy" rows,
    # ride-share office accounts, etc.) and the user wants imports to accept those.
    op.alter_column("drivers", "name", existing_type=sa.String(200), nullable=True)
    op.alter_column("drivers", "phone", existing_type=sa.String(20), nullable=True,
                    type_=sa.String(30))
    # Drop the unique constraint on phone if it exists (Postgres auto-named).
    op.execute("ALTER TABLE drivers DROP CONSTRAINT IF EXISTS drivers_phone_key")
    op.alter_column("drivers", "city", existing_type=sa.String(20), nullable=True)

    # Identity
    op.add_column("drivers", sa.Column("first_name", sa.String(100), nullable=True))
    op.add_column("drivers", sa.Column("last_name",  sa.String(100), nullable=True))
    op.add_column("drivers", sa.Column("aka",        sa.String(100), nullable=True))
    op.add_column("drivers", sa.Column("gender",     sa.String(10),  nullable=True))
    op.add_column("drivers", sa.Column("address",    sa.Text,        nullable=True))
    op.add_column("drivers", sa.Column("mobile",     sa.String(30),  nullable=True))

    # Licensing
    op.add_column("drivers", sa.Column("badge_type",          sa.String(50), nullable=True))
    op.add_column("drivers", sa.Column("school_badge_expiry", sa.Date,        nullable=True))
    op.add_column("drivers", sa.Column("ni_number",           sa.String(50),  nullable=True))

    # Status flags
    op.add_column("drivers", sa.Column("is_active_flag",
                                      sa.Boolean, nullable=False, server_default=sa.text("false")))
    op.add_column("drivers", sa.Column("is_deleted",
                                      sa.Boolean, nullable=False, server_default=sa.text("false")))

    # iCabbi linkage
    op.add_column("drivers", sa.Column("icabbi_ref",   sa.String(50),  nullable=True))
    op.add_column("drivers", sa.Column("vehicle_ref",  sa.String(50),  nullable=True))
    op.add_column("drivers", sa.Column("start_date",   sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_drivers_icabbi_ref", "drivers", ["icabbi_ref"])

    # Device / app metadata
    op.add_column("drivers", sa.Column("imei_udid",                sa.String(200), nullable=True))
    op.add_column("drivers", sa.Column("app_version",              sa.String(50),  nullable=True))
    op.add_column("drivers", sa.Column("legacy_version",           sa.String(50),  nullable=True))
    op.add_column("drivers", sa.Column("installed_legacy_version", sa.String(50),  nullable=True))
    op.add_column("drivers", sa.Column("phone_os",                 sa.String(20),  nullable=True))
    op.add_column("drivers", sa.Column("phone_os_version",         sa.String(50),  nullable=True))
    op.add_column("drivers", sa.Column("phone_manufacturer",       sa.String(100), nullable=True))
    op.add_column("drivers", sa.Column("phone_model",              sa.String(100), nullable=True))
    op.add_column("drivers", sa.Column("phone_locked",
                                      sa.Boolean, nullable=False, server_default=sa.text("false")))
    op.add_column("drivers", sa.Column("profile_photo", sa.String(500), nullable=True))

    # Activity timestamps
    op.add_column("drivers", sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("drivers", sa.Column("last_active_at",  sa.DateTime(timezone=True), nullable=True))

    # Payment metadata
    op.add_column("drivers", sa.Column("frequency",         sa.String(20),  nullable=True))
    op.add_column("drivers", sa.Column("frequency_day",     sa.Integer,     nullable=True))
    op.add_column("drivers", sa.Column("payment_type",      sa.String(50),  nullable=True))
    op.add_column("drivers", sa.Column("payment_period",    sa.Integer,     nullable=True))
    op.add_column("drivers", sa.Column("payment_terms",     sa.Integer,     nullable=True))
    op.add_column("drivers", sa.Column("last_payment_at",   sa.DateTime(timezone=True), nullable=True))
    op.add_column("drivers", sa.Column("output_preference", sa.String(50),  nullable=True))
    op.add_column("drivers", sa.Column("si_id",             sa.String(50),  nullable=True))
    op.add_column("drivers", sa.Column("driver_type",       sa.String(50),  nullable=True,
                                      server_default="regular"))

    # Catch-all for the ~30 deep iCabbi app-config flags (queue, sync_delay,
    # gps_use_network, require_engaged_destination, etc.)
    op.add_column("drivers", sa.Column("icabbi_config", sa.JSON, nullable=True))


def downgrade() -> None:
    op.drop_index("ix_drivers_icabbi_ref", table_name="drivers")
    for col in [
        "icabbi_config", "driver_type", "si_id", "output_preference",
        "last_payment_at", "payment_terms", "payment_period", "payment_type",
        "frequency_day", "frequency",
        "last_active_at", "last_updated_at",
        "profile_photo", "phone_locked", "phone_model", "phone_manufacturer",
        "phone_os_version", "phone_os", "installed_legacy_version",
        "legacy_version", "app_version", "imei_udid",
        "start_date", "vehicle_ref", "icabbi_ref",
        "is_deleted", "is_active_flag",
        "ni_number", "school_badge_expiry", "badge_type",
        "mobile", "address", "gender", "aka", "last_name", "first_name",
    ]:
        op.drop_column("drivers", col)
    # Reinstate constraints
    op.alter_column("drivers", "city", existing_type=sa.String(20), nullable=False)
    op.alter_column("drivers", "phone", existing_type=sa.String(30),
                    type_=sa.String(20), nullable=False)
    op.create_unique_constraint("drivers_phone_key", "drivers", ["phone"])
    op.alter_column("drivers", "name", existing_type=sa.String(200), nullable=False)
