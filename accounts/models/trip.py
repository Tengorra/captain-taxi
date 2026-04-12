"""
Shared Trip model — mirrors the dispatch agent's trips table.
Accounts agent reads from this; dispatch agent writes to it.
"""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Integer, String, Numeric, DateTime, Boolean,
    ForeignKey, Index, Enum as SAEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from database import Base


class TripStatus(str, enum.Enum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)  # iCabbi ID

    # Parties
    driver_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("drivers.id"), index=True)
    corporate_account_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("corporate_accounts.id"), index=True)

    # Location
    city: Mapped[str] = mapped_column(String(50), default="Saskatoon")  # Saskatoon | Regina
    pickup_address: Mapped[str | None] = mapped_column(String(255))
    dropoff_address: Mapped[str | None] = mapped_column(String(255))

    # Financials
    fare: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    gst_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    tip: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    payment_method: Mapped[str | None] = mapped_column(String(30))  # cash | card | account

    # Status
    status: Mapped[TripStatus] = mapped_column(SAEnum(TripStatus), default=TripStatus.PENDING)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    # QB sync
    qb_synced: Mapped[bool] = mapped_column(Boolean, default=False)
    qb_income_id: Mapped[str | None] = mapped_column(String(100))

    # Relationships
    driver: Mapped["Driver"] = relationship("Driver", back_populates="trips")

    __table_args__ = (
        Index("ix_trips_completed_at", "completed_at"),
        Index("ix_trips_driver_completed", "driver_id", "completed_at"),
        Index("ix_trips_corporate_completed", "corporate_account_id", "completed_at"),
    )
