"""Initial schema — drivers, trips, location_history

Revision ID: 001
Revises:
Create Date: 2026-04-08
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    return sa.inspect(bind).has_table(name)


def upgrade() -> None:
    if _table_exists("drivers"):
        # Root alembic chain (alembic/versions/001+002+003) already created
        # `drivers` and `trips` on the shared database. Skip the table/enum
        # creates here so dispatch's chain only contributes `location_history`.
        # When dispatch runs against its own DB, root tables won't exist and
        # the rest of this function runs as written.
        _upgrade_location_history_only()
        return

    op.create_table(
        "drivers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False, unique=True),
        sa.Column("vehicle_plate", sa.String(20), nullable=False),
        sa.Column("vehicle_model", sa.String(80), nullable=False, server_default=""),
        sa.Column("city", sa.String(20), nullable=False),
        sa.Column(
            "status",
            sa.Enum("online", "offline", "on_trip", "break", name="driverstatus"),
            nullable=False,
            server_default="offline",
        ),
        sa.Column("rating", sa.Float, nullable=False, server_default="5.0"),
        sa.Column("total_trips", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_lat", sa.Float, nullable=True),
        sa.Column("last_lng", sa.Float, nullable=True),
        sa.Column("last_location_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_drivers_city", "drivers", ["city"])
    op.create_index("ix_drivers_status", "drivers", ["status"])

    op.create_table(
        "trips",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("customer_name", sa.String(120), nullable=False, server_default=""),
        sa.Column("customer_phone", sa.String(20), nullable=False),
        sa.Column("pickup_address", sa.String(300), nullable=False),
        sa.Column("pickup_lat", sa.Float, nullable=True),
        sa.Column("pickup_lng", sa.Float, nullable=True),
        sa.Column("dropoff_address", sa.String(300), nullable=False),
        sa.Column("dropoff_lat", sa.Float, nullable=True),
        sa.Column("dropoff_lng", sa.Float, nullable=True),
        sa.Column("city", sa.String(20), nullable=False),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column("fare_estimate", sa.Float, nullable=True),
        sa.Column("fare_final", sa.Float, nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "assigned", "en_route", "arrived",
                "in_progress", "completed", "cancelled",
                name="tripstatus",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "booking_source",
            sa.Enum("phone", "app", "web", "whatsapp", "agent", name="bookingsource"),
            nullable=False,
            server_default="agent",
        ),
        sa.Column("driver_id", sa.String(36), sa.ForeignKey("drivers.id"), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assignment_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ai_reasoning", sa.Text, nullable=False, server_default=""),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("driver_en_route_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("driver_arrived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pickup_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.String(300), nullable=False, server_default=""),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_trips_status", "trips", ["status"])
    op.create_index("ix_trips_city", "trips", ["city"])
    op.create_index("ix_trips_driver_id", "trips", ["driver_id"])
    op.create_index("ix_trips_requested_at", "trips", ["requested_at"])

    op.create_table(
        "location_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("driver_id", sa.String(36), sa.ForeignKey("drivers.id"), nullable=False),
        sa.Column("trip_id", sa.String(36), sa.ForeignKey("trips.id"), nullable=True),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lng", sa.Float, nullable=False),
        sa.Column("speed_kmh", sa.Float, nullable=True),
        sa.Column("heading", sa.Float, nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_location_history_driver_id", "location_history", ["driver_id"])
    op.create_index("ix_location_history_trip_id", "location_history", ["trip_id"])
    op.create_index("ix_location_history_recorded_at", "location_history", ["recorded_at"])


def _upgrade_location_history_only() -> None:
    if _table_exists("location_history"):
        return
    op.create_table(
        "location_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("driver_id", sa.String(36), sa.ForeignKey("drivers.id"), nullable=False),
        sa.Column("trip_id", sa.String(36), sa.ForeignKey("trips.id"), nullable=True),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lng", sa.Float, nullable=False),
        sa.Column("speed_kmh", sa.Float, nullable=True),
        sa.Column("heading", sa.Float, nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_location_history_driver_id", "location_history", ["driver_id"])
    op.create_index("ix_location_history_trip_id", "location_history", ["trip_id"])
    op.create_index("ix_location_history_recorded_at", "location_history", ["recorded_at"])


def downgrade() -> None:
    op.drop_table("location_history")
    if _table_exists("trips"):
        op.drop_table("trips")
    if _table_exists("drivers"):
        op.drop_table("drivers")
    op.execute("DROP TYPE IF EXISTS tripstatus")
    op.execute("DROP TYPE IF EXISTS driverstatus")
    op.execute("DROP TYPE IF EXISTS bookingsource")
