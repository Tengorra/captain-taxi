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
    name = Column(String(200), nullable=False)
    phone = Column(String(20), nullable=False, unique=True)
    email = Column(String(200))
    license_number = Column(String(50))
    license_expiry = Column(Date)
    taxi_license_number = Column(String(50))
    taxi_license_expiry = Column(Date)
    status = Column(String(20), nullable=False, default="onboarding")
    city = Column(String(20), nullable=False)
    icabbi_driver_id = Column(String(100))
    rating = Column(Float, default=5.0)
    total_trips = Column(Integer, default=0)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))
    # Admin-managed columns added via ALTER TABLE IF NOT EXISTS
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
