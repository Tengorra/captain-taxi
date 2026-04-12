"""
SQLAlchemy ORM models for the Customer Service Agent.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, String, DateTime, Boolean, Integer, Float,
    Text, ForeignKey, Enum, JSON, Index, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ── Enums ──────────────────────────────────────────────────────────────────────

class Channel(str, PyEnum):
    PHONE    = "phone"
    WHATSAPP = "whatsapp"
    SMS      = "sms"
    WEB_CHAT = "web_chat"

class BookingStatus(str, PyEnum):
    PENDING    = "pending"
    CONFIRMED  = "confirmed"
    DISPATCHED = "dispatched"
    COMPLETED  = "completed"
    CANCELLED  = "cancelled"

class ComplaintSeverity(str, PyEnum):
    MINOR   = "minor"     # auto-resolve with apology + discount
    SERIOUS = "serious"   # escalate to owner immediately

class ComplaintStatus(str, PyEnum):
    OPEN       = "open"
    ESCALATED  = "escalated"
    RESOLVED   = "resolved"


# ── Customers ──────────────────────────────────────────────────────────────────

class Customer(Base):
    __tablename__ = "customers"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone           = Column(String(20), unique=True, nullable=False, index=True)
    name            = Column(String(100))
    email           = Column(String(200))
    preferred_area  = Column(String(100))   # e.g. "Stonebridge", "Airport"
    is_flagged      = Column(Boolean, default=False)   # Repeat complainers / bad actors
    flag_reason     = Column(Text)
    notes           = Column(Text)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())

    bookings    = relationship("Booking",   back_populates="customer", lazy="select")
    complaints  = relationship("Complaint", back_populates="customer", lazy="select")


# ── Bookings ───────────────────────────────────────────────────────────────────

class Booking(Base):
    __tablename__ = "bookings"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id         = Column(String(50), unique=True, index=True)   # iCabbi trip ID
    customer_id     = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    channel         = Column(Enum(Channel), nullable=False)
    pickup_address  = Column(String(300), nullable=False)
    dropoff_address = Column(String(300), nullable=False)
    pickup_time     = Column(DateTime(timezone=True))   # None = ASAP
    num_passengers  = Column(Integer, default=1)
    notes           = Column(Text)
    fare_estimate   = Column(Float)
    status          = Column(Enum(BookingStatus), default=BookingStatus.PENDING)
    dispatch_ref    = Column(JSON)   # Raw response from Dispatch Agent
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())

    customer = relationship("Customer", back_populates="bookings")

    __table_args__ = (
        Index("ix_bookings_customer_created", "customer_id", "created_at"),
    )


# ── Complaints ─────────────────────────────────────────────────────────────────

class Complaint(Base):
    __tablename__ = "complaints"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    trip_id     = Column(String(50), index=True)
    channel     = Column(Enum(Channel), nullable=False)
    description = Column(Text, nullable=False)
    severity    = Column(Enum(ComplaintSeverity), nullable=False)
    status      = Column(Enum(ComplaintStatus), default=ComplaintStatus.OPEN)
    discount_code       = Column(String(20))
    resolution_notes    = Column(Text)
    escalated_at        = Column(DateTime(timezone=True))
    created_at          = Column(DateTime(timezone=True), server_default=func.now())

    customer = relationship("Customer", back_populates="complaints")


# ── Conversations (audit log) ──────────────────────────────────────────────────

class ConversationLog(Base):
    __tablename__ = "conversation_logs"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id  = Column(String(100), index=True, nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"))
    channel     = Column(Enum(Channel), nullable=False)
    messages    = Column(JSON, default=list)   # List of {role, content, ts}
    started_at  = Column(DateTime(timezone=True), server_default=func.now())
    ended_at    = Column(DateTime(timezone=True))
