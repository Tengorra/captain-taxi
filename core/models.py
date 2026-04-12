"""
Shared database models used by all Captain Taxi agents.
"""
import enum
import uuid
from datetime import datetime, date

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, Enum, Float, ForeignKey,
    Integer, String, Text, JSON, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


def new_uuid() -> str:
    return str(uuid.uuid4())


# ─────────────────────────── Enums ────────────────────────────────────────────

class DriverStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"
    ONBOARDING = "onboarding"


class TripStatus(str, enum.Enum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    PICKED_UP = "picked_up"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class DocumentStatus(str, enum.Enum):
    VALID = "valid"
    EXPIRING_SOON = "expiring_soon"   # within 30 days
    EXPIRED = "expired"
    MISSING = "missing"
    UNDER_REVIEW = "under_review"


class EscalationStatus(str, enum.Enum):
    OPEN = "open"
    NOTIFIED = "notified"
    RESOLVED = "resolved"


class City(str, enum.Enum):
    SASKATOON = "saskatoon"
    REGINA = "regina"


# ─────────────────────────── Customer ─────────────────────────────────────────

class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(200))
    preferred_city: Mapped[str | None] = mapped_column(Enum(City))
    notes: Mapped[str | None] = mapped_column(Text)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    trips: Mapped[list["Trip"]] = relationship("Trip", back_populates="customer")


# ─────────────────────────── Driver ───────────────────────────────────────────

class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(200))
    license_number: Mapped[str | None] = mapped_column(String(50))
    license_expiry: Mapped[date | None] = mapped_column(Date)
    taxi_license_number: Mapped[str | None] = mapped_column(String(50))
    taxi_license_expiry: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Enum(DriverStatus), default=DriverStatus.ONBOARDING, nullable=False)
    city: Mapped[str] = mapped_column(Enum(City), nullable=False)
    icabbi_driver_id: Mapped[str | None] = mapped_column(String(100))  # iCabbi/Autocab ID
    rating: Mapped[float | None] = mapped_column(Float)
    total_trips: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    vehicles: Mapped[list["Vehicle"]] = relationship("Vehicle", back_populates="driver")
    trips: Mapped[list["Trip"]] = relationship("Trip", back_populates="driver")
    documents: Mapped[list["Document"]] = relationship(
        "Document", primaryjoin="and_(Driver.id==Document.entity_id, Document.entity_type=='driver')",
        foreign_keys="Document.entity_id", overlaps="documents",
    )


# ─────────────────────────── Vehicle ──────────────────────────────────────────

class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    plate: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    make: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(100))
    year: Mapped[int] = mapped_column(Integer)
    color: Mapped[str | None] = mapped_column(String(50))
    driver_id: Mapped[str | None] = mapped_column(ForeignKey("drivers.id", ondelete="SET NULL"))
    insurance_expiry: Mapped[date | None] = mapped_column(Date)
    registration_expiry: Mapped[date | None] = mapped_column(Date)
    safety_inspection_expiry: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    city: Mapped[str] = mapped_column(Enum(City), nullable=False)
    icabbi_vehicle_id: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    driver: Mapped["Driver | None"] = relationship("Driver", back_populates="vehicles")


# ─────────────────────────── Trip ─────────────────────────────────────────────

class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"))
    driver_id: Mapped[str | None] = mapped_column(ForeignKey("drivers.id", ondelete="SET NULL"))
    pickup_address: Mapped[str] = mapped_column(Text, nullable=False)
    pickup_lat: Mapped[float | None] = mapped_column(Float)
    pickup_lon: Mapped[float | None] = mapped_column(Float)
    dropoff_address: Mapped[str] = mapped_column(Text, nullable=False)
    dropoff_lat: Mapped[float | None] = mapped_column(Float)
    dropoff_lon: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(Enum(TripStatus), default=TripStatus.PENDING, nullable=False)
    fare: Mapped[float | None] = mapped_column(Float)
    distance_km: Mapped[float | None] = mapped_column(Float)
    city: Mapped[str] = mapped_column(Enum(City), nullable=False)
    booking_channel: Mapped[str | None] = mapped_column(String(50))  # phone, app, website, whatsapp
    icabbi_trip_id: Mapped[str | None] = mapped_column(String(100))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    picked_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    customer: Mapped["Customer | None"] = relationship("Customer", back_populates="trips")
    driver: Mapped["Driver | None"] = relationship("Driver", back_populates="trips")


# ─────────────────────────── Document ─────────────────────────────────────────

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # driver, vehicle, company
    doc_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # e.g.: drivers_abstract, insurance, taxi_license, vehicle_registration, criminal_check
    expiry_date: Mapped[date | None] = mapped_column(Date)
    file_path: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(Enum(DocumentStatus), default=DocumentStatus.MISSING)
    notes: Mapped[str | None] = mapped_column(Text)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ─────────────────────────── AgentLog ─────────────────────────────────────────

class AgentLog(Base):
    __tablename__ = "agent_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(500), nullable=False)
    result: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[dict | None] = mapped_column(JSON)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


# ─────────────────────────── Escalation ───────────────────────────────────────

class Escalation(Base):
    __tablename__ = "escalations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    agent: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="high")  # low, medium, high, critical
    status: Mapped[str] = mapped_column(
        Enum(EscalationStatus), default=EscalationStatus.OPEN, nullable=False
    )
    notified_owner: Mapped[bool] = mapped_column(Boolean, default=False)
    notified_amara: Mapped[bool] = mapped_column(Boolean, default=False)
    owner_response: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
