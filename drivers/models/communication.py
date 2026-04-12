import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    String, Integer, Boolean, DateTime, Text, Enum as SAEnum, ForeignKey
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base
from models.driver import City


class MessageDirection(str, enum.Enum):
    OUTBOUND = "outbound"  # agent → driver
    INBOUND = "inbound"    # driver → agent


class MessageChannel(str, enum.Enum):
    SMS = "sms"
    EMAIL = "email"


class MessageStatus(str, enum.Enum):
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    NEEDS_HUMAN = "needs_human"   # agent couldn't handle; escalated to owner


class Message(Base):
    """Individual message to/from a driver."""
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True)
    direction: Mapped[MessageDirection] = mapped_column(SAEnum(MessageDirection))
    channel: Mapped[MessageChannel] = mapped_column(SAEnum(MessageChannel))
    status: Mapped[MessageStatus] = mapped_column(
        SAEnum(MessageStatus), default=MessageStatus.QUEUED
    )
    body: Mapped[str] = mapped_column(Text)
    twilio_sid: Mapped[Optional[str]] = mapped_column(String(100))
    subject: Mapped[Optional[str]] = mapped_column(String(255))  # for email
    agent_response: Mapped[Optional[str]] = mapped_column(Text)  # AI-generated reply
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    driver: Mapped["Driver"] = relationship(back_populates="messages")


class Broadcast(Base):
    """A mass message sent to all or a subset of drivers."""
    __tablename__ = "broadcasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject: Mapped[Optional[str]] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    channel: Mapped[MessageChannel] = mapped_column(SAEnum(MessageChannel))
    city_filter: Mapped[Optional[City]] = mapped_column(SAEnum(City))  # None = all cities
    sent_by: Mapped[str] = mapped_column(String(100), default="agent")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    recipients: Mapped[list["BroadcastRecipient"]] = relationship(
        back_populates="broadcast", cascade="all, delete-orphan"
    )


class BroadcastRecipient(Base):
    __tablename__ = "broadcast_recipients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    broadcast_id: Mapped[int] = mapped_column(ForeignKey("broadcasts.id"), index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True)
    status: Mapped[MessageStatus] = mapped_column(
        SAEnum(MessageStatus), default=MessageStatus.QUEUED
    )
    twilio_sid: Mapped[Optional[str]] = mapped_column(String(100))
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    broadcast: Mapped["Broadcast"] = relationship(back_populates="recipients")
    driver: Mapped["Driver"] = relationship()
