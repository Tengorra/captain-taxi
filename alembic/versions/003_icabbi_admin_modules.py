"""Add iCabbi MANAGE + ADMIN tab modules: addresses, areas, custom fields,
favourites, items, partners, blacklist, receipts, owner_statements, staff.

Revision ID: 003
Revises: 002
Create Date: 2026-05-18
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "addresses",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("label", sa.String(200)),
        sa.Column("line1", sa.String(255), nullable=False),
        sa.Column("line2", sa.String(255)),
        sa.Column("city", sa.String(50)),
        sa.Column("province", sa.String(20), server_default="SK"),
        sa.Column("postal", sa.String(20)),
        sa.Column("lat", sa.Float),
        sa.Column("lng", sa.Float),
        sa.Column("address_type", sa.String(30), server_default="other"),
        sa.Column("customer_id", sa.String(36), index=True),
        sa.Column("notes", sa.Text),
        sa.Column("icabbi_ref", sa.String(50), index=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "areas",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("area_type", sa.String(20), server_default="circle"),
        sa.Column("city", sa.String(50)),
        sa.Column("center_lat", sa.Float),
        sa.Column("center_lng", sa.Float),
        sa.Column("radius_m", sa.Integer),
        sa.Column("polygon_geojson", postgresql.JSONB),
        sa.Column("tags", postgresql.JSONB, server_default="[]"),
        sa.Column("active", sa.Boolean, server_default=sa.true()),
        sa.Column("icabbi_ref", sa.String(50), index=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "custom_field_defs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("entity_type", sa.String(30), nullable=False, index=True),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("data_type", sa.String(20), server_default="string"),
        sa.Column("options", postgresql.JSONB, server_default="[]"),
        sa.Column("required", sa.Boolean, server_default=sa.false()),
        sa.Column("icabbi_ref", sa.String(50), index=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("entity_type", "key", name="uq_custom_field_entity_key"),
    )

    op.create_table(
        "custom_field_values",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("field_id", sa.Integer, nullable=False, index=True),
        sa.Column("entity_id", sa.String(36), nullable=False, index=True),
        sa.Column("value", sa.Text),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("field_id", "entity_id", name="uq_cfv_field_entity"),
    )

    op.create_table(
        "favourites",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("customer_id", sa.String(36), nullable=False, index=True),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("address_text", sa.Text, nullable=False),
        sa.Column("lat", sa.Float),
        sa.Column("lng", sa.Float),
        sa.Column("address_id", sa.Integer),
        sa.Column("times_used", sa.Integer, server_default="0"),
        sa.Column("icabbi_ref", sa.String(50), index=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "items",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(50), unique=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("price", sa.Float, nullable=False, server_default="0"),
        sa.Column("taxable", sa.Boolean, server_default=sa.true()),
        sa.Column("active", sa.Boolean, server_default=sa.true()),
        sa.Column("icabbi_ref", sa.String(50), index=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "partners",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("contact_name", sa.String(200)),
        sa.Column("contact_phone", sa.String(30)),
        sa.Column("contact_email", sa.String(200)),
        sa.Column("city", sa.String(50)),
        sa.Column("commission_rate", sa.Float, server_default="0.10"),
        sa.Column("active", sa.Boolean, server_default=sa.true()),
        sa.Column("notes", sa.Text),
        sa.Column("icabbi_ref", sa.String(50), index=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "blacklist_entries",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("entity_type", sa.String(20), nullable=False, index=True),
        sa.Column("entity_value", sa.String(200), nullable=False, index=True),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("added_by", sa.String(100), server_default="system"),
        sa.Column("active", sa.Boolean, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "receipts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("trip_id", sa.String(36), nullable=False, index=True),
        sa.Column("customer_id", sa.String(36), index=True),
        sa.Column("subtotal", sa.Float, server_default="0"),
        sa.Column("tax", sa.Float, server_default="0"),
        sa.Column("total", sa.Float, server_default="0"),
        sa.Column("items_json", postgresql.JSONB, server_default="[]"),
        sa.Column("file_path", sa.String(500)),
        sa.Column("sent_to_email", sa.String(200)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("icabbi_ref", sa.String(50), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "owner_statements",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("owner_name", sa.String(200), nullable=False),
        sa.Column("owner_email", sa.String(200)),
        sa.Column("vehicle_ref", sa.String(50), index=True),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("gross", sa.Float, server_default="0"),
        sa.Column("deductions", sa.Float, server_default="0"),
        sa.Column("net", sa.Float, server_default="0"),
        sa.Column("status", sa.String(20), server_default="draft"),
        sa.Column("pdf_path", sa.String(500)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "staff",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(200), unique=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("phone", sa.String(30)),
        sa.Column("role", sa.String(20), server_default="viewer"),
        sa.Column("is_active", sa.Boolean, server_default=sa.true()),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    for t in [
        "staff", "owner_statements", "receipts", "blacklist_entries",
        "partners", "items", "favourites",
        "custom_field_values", "custom_field_defs",
        "areas", "addresses",
    ]:
        op.drop_table(t)
