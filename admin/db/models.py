"""
Admin DB models that reflect the actual Captain Taxi database schema.
Shared tables (drivers, trips, vehicles, documents, escalations) use the schema
created by the dispatch/drivers agents.  Admin-only tables (alerts, driver_earnings,
settings, announcements) are created by admin at startup.
"""
from sqlalchemy import (
    Column, Integer, BigInteger, String, Float, Boolean,
    DateTime, Text, Date, JSON,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


# ─── Shared tables (pre-existing schema) ─────────────────────────────────────

class Driver(Base):
    __tablename__ = "drivers"
    id = Column(String(36), primary_key=True)
    # Identity
    name = Column(String(200))                       # display name; built from first+last on import
    first_name = Column(String(100))
    last_name = Column(String(100))
    aka = Column(String(100))
    gender = Column(String(10))
    address = Column(Text)
    email = Column(String(200))
    phone = Column(String(30))                       # iCabbi "Phone" column (was unique+NOT NULL — relaxed)
    mobile = Column(String(30))                      # iCabbi "MOBILE" column (separate from Phone)
    # Licensing
    license_number = Column(String(50))              # driving licence
    license_expiry = Column(Date)
    taxi_license_number = Column(String(50))         # BADGE/PSV
    taxi_license_expiry = Column(Date)
    badge_type = Column(String(50))                  # HACKNEY / PRIVATE HIRE
    school_badge_expiry = Column(Date)
    ni_number = Column(String(50))
    # Status
    status = Column(String(20), nullable=False, default="onboarding")
    is_active_flag = Column(Boolean, default=False)  # iCabbi ACTIVE column (0/1)
    is_deleted = Column(Boolean, default=False)      # iCabbi DELETED column
    city = Column(String(20))
    # iCabbi linkage
    icabbi_driver_id = Column(String(100))           # internal iCabbi DRIVER id (e.g. 34024)
    icabbi_ref = Column(String(50), index=True)      # iCabbi REF (e.g. 7136) — used for de-duplication
    vehicle_ref = Column(String(50))                 # iCabbi Vehicle column (e.g. t1000, 82_old)
    start_date = Column(DateTime(timezone=True))
    # Device / app
    imei_udid = Column(String(200))
    app_version = Column(String(50))
    legacy_version = Column(String(50))
    installed_legacy_version = Column(String(50))
    phone_os = Column(String(20))
    phone_os_version = Column(String(50))
    phone_manufacturer = Column(String(100))
    phone_model = Column(String(100))
    phone_locked = Column(Boolean, default=False)
    profile_photo = Column(String(500))
    # Activity
    last_updated_at = Column(DateTime(timezone=True))   # iCabbi LAST UPDATED
    last_active_at = Column(DateTime(timezone=True))    # iCabbi LAST ACTIVE
    # Payments
    frequency = Column(String(20))                   # MONTHLY / WEEKLY
    frequency_day = Column(Integer)
    payment_type = Column(String(50))                # CASH / BANK_TRANSFER / CARD
    payment_period = Column(Integer)
    payment_terms = Column(Integer)
    last_payment_at = Column(DateTime(timezone=True))
    output_preference = Column(String(50))           # EMAIL etc.
    si_id = Column(String(50))
    # Catch-all for the ~30 deep iCabbi app-config flags (sync_delay, queue,
    # job_timeout, gps_use_network, etc.) — stored verbatim, not first-classed
    icabbi_config = Column(JSON)
    # Misc
    rating = Column(Float, default=5.0)
    total_trips = Column(Integer, default=0)
    notes = Column(Text)
    driver_type = Column(String(50), default="regular")
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))
    performance_score = Column(Float, default=100.0)
    commission_rate = Column(Float, default=0.30)


class Vehicle(Base):
    __tablename__ = "vehicles"
    id = Column(String(36), primary_key=True)
    plate = Column(String(20), unique=True, nullable=False)
    make = Column(String(100), nullable=False)
    model = Column(String(100), nullable=False)
    year = Column(Integer, nullable=False)
    color = Column(String(50))
    driver_id = Column(String(36))
    insurance_expiry = Column(Date)
    registration_expiry = Column(Date)
    safety_inspection_expiry = Column(Date)
    is_active = Column(Boolean, default=True)
    city = Column(String(20), nullable=False)
    icabbi_vehicle_id = Column(String(100))
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))


class Trip(Base):
    __tablename__ = "trips"
    id = Column(String(36), primary_key=True)
    customer_id = Column(String(36))
    driver_id = Column(String(36))
    city = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    pickup_address = Column(Text, nullable=False)
    dropoff_address = Column(Text, nullable=False)
    fare = Column(Float)
    distance_km = Column(Float)
    booking_channel = Column(String(50))
    icabbi_trip_id = Column(String(100))
    scheduled_at = Column(DateTime(timezone=True))
    dispatched_at = Column(DateTime(timezone=True))
    picked_up_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True))


class Document(Base):
    """Generic entity document – filter on entity_type='driver' for driver docs."""
    __tablename__ = "documents"
    id = Column(String(36), primary_key=True)
    entity_id = Column(String(36), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False, index=True)
    doc_type = Column(String(100), nullable=False)
    expiry_date = Column(Date)
    file_path = Column(String(500))
    status = Column(String(30), nullable=False, default="missing")
    notes = Column(Text)
    uploaded_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))


class Escalation(Base):
    """Escalation table created by compliance/dispatch agents."""
    __tablename__ = "escalations"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    agent = Column(String(100), nullable=False)
    reason = Column(String(500), nullable=False)
    details = Column(Text, nullable=False)
    priority = Column(String(20), nullable=False, default="high")
    status = Column(String(20), nullable=False, default="open")  # open/resolved
    notified_owner = Column(Boolean, nullable=False, default=False)
    notified_amara = Column(Boolean, nullable=False, default=False)
    owner_response = Column(Text)
    resolved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))


# ─── Admin-only tables (created by admin at startup) ─────────────────────────

class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    severity = Column(String(20), default="medium")   # low/medium/high/critical
    source_agent = Column(String(50))
    is_read = Column(Boolean, default=False)
    is_resolved = Column(Boolean, default=False)
    driver_id = Column(String(36))
    extra = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True))


class DriverEarning(Base):
    __tablename__ = "driver_earnings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    driver_id = Column(String(36))
    week_start = Column(DateTime(timezone=True), nullable=False)
    gross_earnings = Column(Float, default=0.0)
    commission = Column(Float, default=0.0)
    net_earnings = Column(Float, default=0.0)
    trips_count = Column(Integer, default=0)
    paid = Column(Boolean, default=False)
    paid_at = Column(DateTime(timezone=True))


class Announcement(Base):
    __tablename__ = "announcements"
    id = Column(Integer, primary_key=True, autoincrement=True)
    message = Column(Text, nullable=False)
    target_city = Column(String(20))
    sent_by = Column(String(50), default="owner")
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    delivery_count = Column(Integer, default=0)


class Settings(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=False)
    description = Column(String(300))
    updated_at = Column(DateTime(timezone=True))


# ─── iCabbi MANAGE-tab modules ───────────────────────────────────────────────
# All carry icabbi_ref + last_synced_at so a future sync job can reconcile rows
# pulled from iCabbi without duplicating them.

class Address(Base):
    __tablename__ = "addresses"
    id = Column(Integer, primary_key=True, autoincrement=True)
    label = Column(String(200))                          # "Home", "City Hall", etc.
    line1 = Column(String(255), nullable=False)
    line2 = Column(String(255))
    city = Column(String(50))
    province = Column(String(20), default="SK")
    postal = Column(String(20))
    lat = Column(Float)
    lng = Column(Float)
    address_type = Column(String(30), default="other")   # home/work/landmark/other
    customer_id = Column(String(36), index=True)         # null = global address
    notes = Column(Text)
    icabbi_ref = Column(String(50), index=True)
    last_synced_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True))


class Area(Base):
    __tablename__ = "areas"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    area_type = Column(String(20), default="circle")     # circle / polygon
    city = Column(String(50))
    # circle:
    center_lat = Column(Float)
    center_lng = Column(Float)
    radius_m = Column(Integer)
    # polygon:
    polygon_geojson = Column(JSON)                       # GeoJSON Polygon coordinates
    tags = Column(JSON, default=list)                    # ["fare_zone", "dispatch", ...]
    active = Column(Boolean, default=True)
    icabbi_ref = Column(String(50), index=True)
    last_synced_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True))


class CustomFieldDef(Base):
    """Schema row: defines a custom field that can be attached to an entity type."""
    __tablename__ = "custom_field_defs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String(30), nullable=False, index=True)  # driver/customer/trip/account/vehicle
    key = Column(String(100), nullable=False)
    label = Column(String(200), nullable=False)
    data_type = Column(String(20), default="string")     # string/number/bool/date/select
    options = Column(JSON, default=list)                 # for select: ["A","B","C"]
    required = Column(Boolean, default=False)
    icabbi_ref = Column(String(50), index=True)
    last_synced_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CustomFieldValue(Base):
    """Value row: one per entity per field."""
    __tablename__ = "custom_field_values"
    id = Column(Integer, primary_key=True, autoincrement=True)
    field_id = Column(Integer, nullable=False, index=True)        # → custom_field_defs.id
    entity_id = Column(String(36), nullable=False, index=True)
    value = Column(Text)
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class Favourite(Base):
    __tablename__ = "favourites"
    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String(36), nullable=False, index=True)
    label = Column(String(200), nullable=False)
    address_text = Column(Text, nullable=False)
    lat = Column(Float)
    lng = Column(Float)
    address_id = Column(Integer)                         # optional → addresses.id
    times_used = Column(Integer, default=0)
    icabbi_ref = Column(String(50), index=True)
    last_synced_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Item(Base):
    """Trip extras catalogue: cleaning fee, child seat, meet-and-greet, etc."""
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    price = Column(Float, nullable=False, default=0.0)
    taxable = Column(Boolean, default=True)
    active = Column(Boolean, default=True)
    icabbi_ref = Column(String(50), index=True)
    last_synced_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Partner(Base):
    """Affiliate operators (sister taxi companies, ride-share handoff partners)."""
    __tablename__ = "partners"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    contact_name = Column(String(200))
    contact_phone = Column(String(30))
    contact_email = Column(String(200))
    city = Column(String(50))
    commission_rate = Column(Float, default=0.10)         # fraction we pay/take
    active = Column(Boolean, default=True)
    notes = Column(Text)
    icabbi_ref = Column(String(50), index=True)
    last_synced_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True))


# ─── iCabbi ADMIN-tab modules ────────────────────────────────────────────────

class BlacklistEntry(Base):
    """Blocked phone numbers / customers / drivers / emails."""
    __tablename__ = "blacklist_entries"
    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String(20), nullable=False, index=True)   # phone/customer/driver/email
    entity_value = Column(String(200), nullable=False, index=True)
    reason = Column(Text, nullable=False)
    expires_at = Column(DateTime(timezone=True))                   # null = permanent
    added_by = Column(String(100), default="system")               # owner/amara/agent name
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Receipt(Base):
    """Customer-facing trip receipts (generated PDFs, sent by email)."""
    __tablename__ = "receipts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    trip_id = Column(String(36), nullable=False, index=True)
    customer_id = Column(String(36), index=True)
    subtotal = Column(Float, default=0.0)
    tax = Column(Float, default=0.0)
    total = Column(Float, default=0.0)
    items_json = Column(JSON, default=list)              # line items snapshot
    file_path = Column(String(500))
    sent_to_email = Column(String(200))
    sent_at = Column(DateTime(timezone=True))
    icabbi_ref = Column(String(50), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class OwnerStatement(Base):
    """Per-vehicle-owner periodic payout statement (distinct from driver pay)."""
    __tablename__ = "owner_statements"
    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_name = Column(String(200), nullable=False)
    owner_email = Column(String(200))
    vehicle_ref = Column(String(50), index=True)         # iCabbi vehicle ref (e.g. t1000)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    gross = Column(Float, default=0.0)
    deductions = Column(Float, default=0.0)
    net = Column(Float, default=0.0)
    status = Column(String(20), default="draft")         # draft/sent/paid
    pdf_path = Column(String(500))
    sent_at = Column(DateTime(timezone=True))
    paid_at = Column(DateTime(timezone=True))
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Staff(Base):
    """Dashboard login accounts — thin (owner, Amara, optional read-only).
    Captain Taxi's AI replaces the iCabbi operator/dispatcher role, so this is
    NOT a full role/permission matrix."""
    __tablename__ = "staff"
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(200), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    phone = Column(String(30))
    role = Column(String(20), default="viewer")          # owner/admin/viewer
    is_active = Column(Boolean, default=True)
    last_login_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
