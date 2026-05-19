"""Add dispatch-service columns to drivers table

Revision ID: 003
Revises: 002
Create Date: 2026-05-19

Migration 001/002 created the drivers table with the columns the
orchestrator/admin services expect (license_number, taxi_license_number,
icabbi fields, etc.), but the dispatch service's Driver model
(dispatch/models/driver.py) needs six extra columns that were previously
expected to be added by SQLAlchemy's create_all() — which doesn't ALTER
existing tables, so they were missing in real deployments.

This migration adds those six columns. All are nullable or have a server
default so the migration is safe to apply to a populated drivers table.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("drivers", sa.Column("vehicle_plate",   sa.String(20), nullable=True))
    op.add_column("drivers", sa.Column("vehicle_model",   sa.String(80), nullable=True))
    op.add_column("drivers", sa.Column("is_active",       sa.Boolean,
                                       nullable=False, server_default=sa.text("true")))
    op.add_column("drivers", sa.Column("last_lat",        sa.Float,     nullable=True))
    op.add_column("drivers", sa.Column("last_lng",        sa.Float,     nullable=True))
    op.add_column("drivers", sa.Column("last_location_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for col in ("last_location_at", "last_lng", "last_lat",
                "is_active", "vehicle_model", "vehicle_plate"):
        op.drop_column("drivers", col)
