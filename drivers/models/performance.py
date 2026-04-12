import enum
from datetime import datetime, date
from typing import Optional
from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, Date, Text, Enum as SAEnum,
    ForeignKey
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class FlagType(str, enum.Enum):
    HIGH_CANCELLATION = "high_cancellation"
    LOW_RATING = "low_rating"
    EXCESSIVE_COMPLAINTS = "excessive_complaints"
    LATE_ARRIVALS = "late_arrivals"


class FlagStatus(str, enum.Enum):
    OPEN = "open"
    WARNING_SENT = "warning_sent"
    ESCALATED = "escalated"
    RESOLVED = "resolved"


class DriverMetrics(Base):
    """Weekly performance snapshot per driver."""
    __tablename__ = "driver_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True)
    week_start: Mapped[date] = mapped_column(Date, index=True)

    trips_completed: Mapped[int] = mapped_column(Integer, default=0)
    trips_cancelled: Mapped[int] = mapped_column(Integer, default=0)
    trips_offered: Mapped[int] = mapped_column(Integer, default=0)
    avg_rating: Mapped[Optional[float]] = mapped_column(Float)
    late_arrivals: Mapped[int] = mapped_column(Integer, default=0)
    complaints_count: Mapped[int] = mapped_column(Integer, default=0)
    income_earned: Mapped[float] = mapped_column(Float, default=0.0)
    hours_online: Mapped[float] = mapped_column(Float, default=0.0)

    # Computed
    cancellation_rate: Mapped[Optional[float]] = mapped_column(Float)
    report_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    report_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    driver: Mapped["Driver"] = relationship(back_populates="metrics")


class PerformanceFlag(Base):
    """A flag raised against a driver for a performance issue."""
    __tablename__ = "performance_flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True)
    flag_type: Mapped[FlagType] = mapped_column(SAEnum(FlagType))
    status: Mapped[FlagStatus] = mapped_column(SAEnum(FlagStatus), default=FlagStatus.OPEN)
    detail: Mapped[Optional[str]] = mapped_column(Text)
    value: Mapped[Optional[float]] = mapped_column(Float)  # the metric value that triggered it
    week_start: Mapped[Optional[date]] = mapped_column(Date)

    warning_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    escalated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    driver: Mapped["Driver"] = relationship(back_populates="flags")


class Complaint(Base):
    """A customer or internal complaint against a driver."""
    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True)
    source: Mapped[str] = mapped_column(String(50))  # "customer", "internal", "dispatch"
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[int] = mapped_column(Integer, default=1)  # 1=minor, 2=moderate, 3=severe
    trip_id: Mapped[Optional[str]] = mapped_column(String(100))
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    driver: Mapped["Driver"] = relationship(back_populates="complaints")
