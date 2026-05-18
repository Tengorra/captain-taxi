"""Full iCabbi driver-record parity: attributes, fatigue, VAT, custom fields,
breathalyser, site assignments. Also extends `vehicles` with the iCabbi
vehicle-dump columns so a vehicle CSV can be imported.

Revision ID: 003
Revises: 002
Create Date: 2026-05-18
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ───────────────────────────── DRIVER PARITY ─────────────────────────────────
DRIVER_NEW_COLUMNS = [
    # Auth (iCabbi Driver ID / Login + Password)
    ("login_username",        sa.String(100), True,  None),
    ("login_password_hash",   sa.String(200), True,  None),
    # Personal
    ("ethnicity",             sa.String(50),  True,  None),
    ("transporter",           sa.Boolean,     False, sa.text("false")),
    # Payment card (last4 + expiry only — never store full PAN)
    ("payment_card_last4",    sa.String(8),   True,  None),
    ("payment_card_expiry",   sa.Date,        True,  None),
    # Custom fields
    ("pvg_disclosure",        sa.Text,        True,  None),
    ("police_record",         sa.Text,        True,  None),
    ("police_record_2",       sa.Text,        True,  None),
    # Attributes (iCabbi YES/NO toggles)
    ("attr_pets",             sa.Boolean,     False, sa.text("false")),
    ("attr_uniformed",        sa.Boolean,     False, sa.text("false")),
    ("attr_topman",           sa.Boolean,     False, sa.text("false")),
    ("attr_accept_discount",  sa.Boolean,     False, sa.text("true")),
    ("attr_accept_account",   sa.Boolean,     False, sa.text("true")),
    ("attr_accept_fixed_fares", sa.Boolean,   False, sa.text("true")),
    ("attr_accept_cash_work", sa.Boolean,     False, sa.text("true")),
    # Device extras
    ("phone_assist",          sa.Boolean,     False, sa.text("false")),
    # Invoicing / Shifts
    ("invoice_footer",        sa.String(100), True,  None),
    ("shift_reporting",       sa.Boolean,     False, sa.text("false")),
    # Payments / VAT
    ("payment_on_day",        sa.String(20),  True,  None),  # MONDAY / SUNDAY
    ("distribution",          sa.String(20),  True,  None),  # POST / EMAIL
    ("apply_vat",             sa.Boolean,     False, sa.text("false")),
    ("vat_rate",              sa.Float,       True,  None),
    ("balance",               sa.Float,       True,  None),
    ("exclude_booking_fee",   sa.Boolean,     False, sa.text("false")),
    ("auto_post",             sa.String(30),  True,  None),  # SYSTEM_DEFAULT / NEVER / ALWAYS
    # Bank
    ("bank_payment_ref",      sa.String(100), True,  None),
    ("use_sepa",              sa.Boolean,     False, sa.text("false")),
    ("bank_name",             sa.String(100), True,  None),
    ("bank_account_name",     sa.String(100), True,  None),
    ("sort_code",             sa.String(20),  True,  None),
    ("bank_account_number",   sa.String(50),  True,  None),
    # Breathalyser
    ("breathalyser_enabled",  sa.Boolean,     False, sa.text("false")),
    # Fatigue
    ("fatigue_max_work_hours", sa.Integer,    True,  None),
    ("fatigue_min_rest_hours", sa.Integer,    True,  None),
    ("fatigue_exceed_job_pct", sa.Integer,    True,  None),
    ("fatigue_send_alert_pct", sa.Integer,    True,  None),
]


# ─────────────────────────── VEHICLE PARITY ──────────────────────────────────
VEHICLE_NEW_COLUMNS = [
    ("vehicle_ref",            sa.String(50),  True,  None),   # iCabbi REF
    ("aka",                    sa.String(50),  True,  None),
    ("internal_system_id",     sa.String(50),  True,  None),
    ("registration",           sa.String(20),  True,  None),
    ("nct_mot_expiry",         sa.DateTime(timezone=True), True, None),
    ("plate_expiry",           sa.DateTime(timezone=True), True, None),
    ("insurer",                sa.String(150), True,  None),
    ("insurance",              sa.String(150), True,  None),
    ("hire_expiry",            sa.DateTime(timezone=True), True, None),
    ("road_tax_expiry",        sa.DateTime(timezone=True), True, None),
    ("council_compliance_expiry", sa.DateTime(timezone=True), True, None),
    ("owner_driver",           sa.Boolean,     False, sa.text("false")),
    ("device_identifier",      sa.String(100), True,  None),
    ("sensors",                sa.String(50),  True,  None),
    ("payment_device",         sa.String(50),  True,  None),
    ("payment_version",        sa.String(50),  True,  None),
    ("light_control",          sa.String(50),  True,  None),
    ("status_control",         sa.String(50),  True,  None),
    ("vehicle_phone",          sa.String(30),  True,  None),
    ("co2_emission",           sa.Float,       True,  None),
    ("credit_card_payments",   sa.Boolean,     False, sa.text("false")),
    ("wifi",                   sa.Boolean,     False, sa.text("false")),
    ("wheelchair",             sa.Boolean,     False, sa.text("false")),
    ("saloon",                 sa.Boolean,     False, sa.text("false")),
    ("executive",              sa.Boolean,     False, sa.text("false")),
    ("good_condition",         sa.Boolean,     False, sa.text("false")),
    ("average_condition",      sa.Boolean,     False, sa.text("false")),
    ("seater_4",               sa.Boolean,     False, sa.text("false")),
    ("seater_5",               sa.Boolean,     False, sa.text("false")),
    ("seater_6",               sa.Boolean,     False, sa.text("false")),
    ("seater_7",               sa.Boolean,     False, sa.text("false")),
    ("seater_8",               sa.Boolean,     False, sa.text("false")),
    ("body_low_rider",         sa.Boolean,     False, sa.text("false")),
    ("body_estate",            sa.Boolean,     False, sa.text("false")),
    ("body_high_rider",        sa.Boolean,     False, sa.text("false")),
    ("body_sedan",             sa.Boolean,     False, sa.text("false")),
    ("body_minivan",           sa.Boolean,     False, sa.text("false")),
    ("body_suv",               sa.Boolean,     False, sa.text("false")),
    ("comments",               sa.Text,        True,  None),
    ("is_deleted",             sa.Boolean,     False, sa.text("false")),
]


def upgrade() -> None:
    # Drivers — add new fields
    for name, type_, nullable, default in DRIVER_NEW_COLUMNS:
        kwargs = {"nullable": nullable}
        if default is not None:
            kwargs["server_default"] = default
        op.add_column("drivers", sa.Column(name, type_, **kwargs))

    # Vehicles — relax plate/make/model NOT NULL (iCabbi exports have blanks);
    # drop unique-on-plate so duplicate rows (vehicle_ref "001" vs "001_Old")
    # don't conflict on the same plate value.
    op.alter_column("vehicles", "plate", existing_type=sa.String(20), nullable=True)
    op.alter_column("vehicles", "make", existing_type=sa.String(100), nullable=True)
    op.alter_column("vehicles", "model", existing_type=sa.String(100), nullable=True)
    op.alter_column("vehicles", "year", existing_type=sa.Integer, nullable=True)
    op.alter_column("vehicles", "city", existing_type=sa.String(20), nullable=True)
    op.execute("ALTER TABLE vehicles DROP CONSTRAINT IF EXISTS vehicles_plate_key")
    for name, type_, nullable, default in VEHICLE_NEW_COLUMNS:
        kwargs = {"nullable": nullable}
        if default is not None:
            kwargs["server_default"] = default
        op.add_column("vehicles", sa.Column(name, type_, **kwargs))
    op.create_index("ix_vehicles_vehicle_ref", "vehicles", ["vehicle_ref"])

    # New table: driver_sites — each driver can be assigned to one or more
    # sites (e.g. CTS — Captain Taxi Saskatoon, CTR — Captain Taxi Regina).
    op.create_table(
        "driver_sites",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("driver_id", sa.String(36), sa.ForeignKey("drivers.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("site_code", sa.String(20), nullable=False),   # CTS / CTR
        sa.Column("site_name", sa.String(100), nullable=False),
        sa.Column("assigned", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("is_primary", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_driver_sites_driver_id_site", "driver_sites",
                    ["driver_id", "site_code"], unique=True)

    # New table: driver_files — uploads (Police Disclosure, Agreement, Photo
    # ID, Licence Photo/Paper, Proof of Address, PCO Licence, Insurance, …).
    # We could overload `documents` for this, but those entries already drive
    # the compliance traffic-light logic — keeping uploads in their own table
    # avoids polluting compliance counts with HR-only docs.
    op.create_table(
        "driver_files",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("driver_id", sa.String(36), sa.ForeignKey("drivers.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("file_type", sa.String(50), nullable=False),
        # police_disclosure, agreement, proof_of_address, photo_id,
        # licence_photo, licence_paper, pco_licence, insurance, other
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("size_bytes", sa.Integer),
        sa.Column("content_type", sa.String(100)),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_driver_files_driver_type", "driver_files",
                    ["driver_id", "file_type"])


def downgrade() -> None:
    op.drop_index("ix_driver_files_driver_type", table_name="driver_files")
    op.drop_table("driver_files")
    op.drop_index("ix_driver_sites_driver_id_site", table_name="driver_sites")
    op.drop_table("driver_sites")

    op.drop_index("ix_vehicles_vehicle_ref", table_name="vehicles")
    for name, *_ in reversed(VEHICLE_NEW_COLUMNS):
        op.drop_column("vehicles", name)
    op.alter_column("vehicles", "city", existing_type=sa.String(20), nullable=False)
    op.alter_column("vehicles", "year", existing_type=sa.Integer, nullable=False)
    op.alter_column("vehicles", "model", existing_type=sa.String(100), nullable=False)
    op.alter_column("vehicles", "make", existing_type=sa.String(100), nullable=False)
    op.alter_column("vehicles", "plate", existing_type=sa.String(20), nullable=False)
    op.create_unique_constraint("vehicles_plate_key", "vehicles", ["plate"])

    for name, *_ in reversed(DRIVER_NEW_COLUMNS):
        op.drop_column("drivers", name)
