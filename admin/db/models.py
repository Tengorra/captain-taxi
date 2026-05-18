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

    # Auth (iCabbi Driver ID / Login + Password)
    login_username = Column(String(100))
    login_password_hash = Column(String(200))
    # Personal extras
    ethnicity = Column(String(50))
    transporter = Column(Boolean, default=False)
    payment_card_last4 = Column(String(8))
    payment_card_expiry = Column(Date)
    # Custom fields
    pvg_disclosure = Column(Text)
    police_record = Column(Text)
    police_record_2 = Column(Text)
    # Attributes (iCabbi yes/no toggles)
    attr_pets = Column(Boolean, default=False)
    attr_uniformed = Column(Boolean, default=False)
    attr_topman = Column(Boolean, default=False)
    attr_accept_discount = Column(Boolean, default=True)
    attr_accept_account = Column(Boolean, default=True)
    attr_accept_fixed_fares = Column(Boolean, default=True)
    attr_accept_cash_work = Column(Boolean, default=True)
    # Device
    phone_assist = Column(Boolean, default=False)
    # Invoicing / Shifts
    invoice_footer = Column(String(100))
    shift_reporting = Column(Boolean, default=False)
    # Payments / VAT
    payment_on_day = Column(String(20))
    distribution = Column(String(20))
    apply_vat = Column(Boolean, default=False)
    vat_rate = Column(Float)
    balance = Column(Float)
    exclude_booking_fee = Column(Boolean, default=False)
    auto_post = Column(String(30))
    # Bank
    bank_payment_ref = Column(String(100))
    use_sepa = Column(Boolean, default=False)
    bank_name = Column(String(100))
    bank_account_name = Column(String(100))
    sort_code = Column(String(20))
    bank_account_number = Column(String(50))
    # Breathalyser
    breathalyser_enabled = Column(Boolean, default=False)
    # Fatigue
    fatigue_max_work_hours = Column(Integer)
    fatigue_min_rest_hours = Column(Integer)
    fatigue_exceed_job_pct = Column(Integer)
    fatigue_send_alert_pct = Column(Integer)


class DriverSite(Base):
    """Site assignments for a driver (CTS = Captain Taxi Saskatoon, CTR = Regina)."""
    __tablename__ = "driver_sites"
    id = Column(String(36), primary_key=True)
    driver_id = Column(String(36), nullable=False, index=True)
    site_code = Column(String(20), nullable=False)
    site_name = Column(String(100), nullable=False)
    assigned = Column(Boolean, nullable=False, default=True)
    is_primary = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True))


class DriverFile(Base):
    """HR-style uploads (Police Disclosure, Agreement, Photo ID, Licence
    Photo/Paper, etc.). Compliance-relevant docs continue to live in
    `documents` so the traffic-light overview stays accurate."""
    __tablename__ = "driver_files"
    id = Column(String(36), primary_key=True)
    driver_id = Column(String(36), nullable=False, index=True)
    file_type = Column(String(50), nullable=False)
    filename = Column(String(255), nullable=False)
    storage_path = Column(String(500), nullable=False)
    size_bytes = Column(Integer)
    content_type = Column(String(100))
    uploaded_at = Column(DateTime(timezone=True))


class Vehicle(Base):
    __tablename__ = "vehicles"
    id = Column(String(36), primary_key=True)
    plate = Column(String(20))
    make = Column(String(100))
    model = Column(String(100))
    year = Column(Integer)
    color = Column(String(50))
    driver_id = Column(String(36))
    insurance_expiry = Column(Date)
    registration_expiry = Column(Date)
    safety_inspection_expiry = Column(Date)
    is_active = Column(Boolean, default=True)
    city = Column(String(20))
    icabbi_vehicle_id = Column(String(100))
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))

    # iCabbi vehicle-dump extras
    vehicle_ref = Column(String(50), index=True)
    aka = Column(String(50))
    internal_system_id = Column(String(50))
    registration = Column(String(20))
    nct_mot_expiry = Column(DateTime(timezone=True))
    plate_expiry = Column(DateTime(timezone=True))
    insurer = Column(String(150))
    insurance = Column(String(150))
    hire_expiry = Column(DateTime(timezone=True))
    road_tax_expiry = Column(DateTime(timezone=True))
    council_compliance_expiry = Column(DateTime(timezone=True))
    owner_driver = Column(Boolean, default=False)
    device_identifier = Column(String(100))
    sensors = Column(String(50))
    payment_device = Column(String(50))
    payment_version = Column(String(50))
    light_control = Column(String(50))
    status_control = Column(String(50))
    vehicle_phone = Column(String(30))
    co2_emission = Column(Float)
    credit_card_payments = Column(Boolean, default=False)
    wifi = Column(Boolean, default=False)
    wheelchair = Column(Boolean, default=False)
    saloon = Column(Boolean, default=False)
    executive = Column(Boolean, default=False)
    good_condition = Column(Boolean, default=False)
    average_condition = Column(Boolean, default=False)
    seater_4 = Column(Boolean, default=False)
    seater_5 = Column(Boolean, default=False)
    seater_6 = Column(Boolean, default=False)
    seater_7 = Column(Boolean, default=False)
    seater_8 = Column(Boolean, default=False)
    body_low_rider = Column(Boolean, default=False)
    body_estate = Column(Boolean, default=False)
    body_high_rider = Column(Boolean, default=False)
    body_sedan = Column(Boolean, default=False)
    body_minivan = Column(Boolean, default=False)
    body_suv = Column(Boolean, default=False)
    comments = Column(Text)
    is_deleted = Column(Boolean, default=False)


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
