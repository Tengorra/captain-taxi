"""Initial schema — all core tables

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


def upgrade() -> None:
    # ── customers ──────────────────────────────────────────────────────────────
    op.create_table(
        "customers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("phone", sa.String(20), nullable=False, unique=True),
        sa.Column("name", sa.String(200)),
        sa.Column("email", sa.String(200)),
        sa.Column("preferred_city", sa.String(20)),
        sa.Column("notes", sa.Text),
        sa.Column("is_blocked", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_customers_phone", "customers", ["phone"])

    # ── drivers ────────────────────────────────────────────────────────────────
    op.create_table(
        "drivers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False, unique=True),
        sa.Column("email", sa.String(200)),
        sa.Column("license_number", sa.String(50)),
        sa.Column("license_expiry", sa.Date),
        sa.Column("taxi_license_number", sa.String(50)),
        sa.Column("taxi_license_expiry", sa.Date),
        sa.Column("status", sa.String(20), nullable=False, server_default="onboarding"),
        sa.Column("city", sa.String(20), nullable=False),
        sa.Column("icabbi_driver_id", sa.String(100)),
        sa.Column("rating", sa.Float),
        sa.Column("total_trips", sa.Integer, nullable=False, server_default="0"),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_drivers_phone", "drivers", ["phone"])
    op.create_index("ix_drivers_status", "drivers", ["status"])
    op.create_index("ix_drivers_city", "drivers", ["city"])

    # ── vehicles ───────────────────────────────────────────────────────────────
    op.create_table(
        "vehicles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("plate", sa.String(20), nullable=False, unique=True),
        sa.Column("make", sa.String(100), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("color", sa.String(50)),
        sa.Column("driver_id", sa.String(36), sa.ForeignKey("drivers.id", ondelete="SET NULL")),
        sa.Column("insurance_expiry", sa.Date),
        sa.Column("registration_expiry", sa.Date),
        sa.Column("safety_inspection_expiry", sa.Date),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("city", sa.String(20), nullable=False),
        sa.Column("icabbi_vehicle_id", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_vehicles_plate", "vehicles", ["plate"])
    op.create_index("ix_vehicles_driver_id", "vehicles", ["driver_id"])

    # ── trips ──────────────────────────────────────────────────────────────────
    op.create_table(
        "trips",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id", ondelete="SET NULL")),
        sa.Column("driver_id", sa.String(36), sa.ForeignKey("drivers.id", ondelete="SET NULL")),
        sa.Column("pickup_address", sa.Text, nullable=False),
        sa.Column("pickup_lat", sa.Float),
        sa.Column("pickup_lon", sa.Float),
        sa.Column("dropoff_address", sa.Text, nullable=False),
        sa.Column("dropoff_lat", sa.Float),
        sa.Column("dropoff_lon", sa.Float),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("fare", sa.Float),
        sa.Column("distance_km", sa.Float),
        sa.Column("city", sa.String(20), nullable=False),
        sa.Column("booking_channel", sa.String(50)),
        sa.Column("icabbi_trip_id", sa.String(100)),
        sa.Column("scheduled_at", sa.DateTime(timezone=True)),
        sa.Column("dispatched_at", sa.DateTime(timezone=True)),
        sa.Column("picked_up_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_trips_customer_id", "trips", ["customer_id"])
    op.create_index("ix_trips_driver_id", "trips", ["driver_id"])
    op.create_index("ix_trips_status", "trips", ["status"])
    op.create_index("ix_trips_city", "trips", ["city"])
    op.create_index("ix_trips_created_at", "trips", ["created_at"])

    # ── documents ──────────────────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("doc_type", sa.String(100), nullable=False),
        sa.Column("expiry_date", sa.Date),
        sa.Column("file_path", sa.String(500)),
        sa.Column("status", sa.String(30), nullable=False, server_default="missing"),
        sa.Column("notes", sa.Text),
        sa.Column("uploaded_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_documents_entity_id", "documents", ["entity_id"])
    op.create_index("ix_documents_entity_type", "documents", ["entity_type"])
    op.create_index("ix_documents_status", "documents", ["status"])
    op.create_index("ix_documents_expiry_date", "documents", ["expiry_date"])

    # ── agent_logs ─────────────────────────────────────────────────────────────
    op.create_table(
        "agent_logs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("agent_name", sa.String(100), nullable=False),
        sa.Column("action", sa.String(500), nullable=False),
        sa.Column("result", sa.Text),
        sa.Column("metadata", sa.JSON),
        sa.Column("success", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("duration_ms", sa.Integer),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_agent_logs_agent_name", "agent_logs", ["agent_name"])
    op.create_index("ix_agent_logs_timestamp", "agent_logs", ["timestamp"])

    # ── escalations ────────────────────────────────────────────────────────────
    op.create_table(
        "escalations",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("agent", sa.String(100), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("details", sa.Text, nullable=False),
        sa.Column("priority", sa.String(20), nullable=False, server_default="high"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("notified_owner", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("notified_amara", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("owner_response", sa.Text),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_escalations_agent", "escalations", ["agent"])
    op.create_index("ix_escalations_status", "escalations", ["status"])
    op.create_index("ix_escalations_created_at", "escalations", ["created_at"])


def downgrade() -> None:
    op.drop_table("escalations")
    op.drop_table("agent_logs")
    op.drop_table("documents")
    op.drop_table("trips")
    op.drop_table("vehicles")
    op.drop_table("drivers")
    op.drop_table("customers")
