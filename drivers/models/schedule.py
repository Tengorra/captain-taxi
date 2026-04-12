import enum
from datetime import datetime, date, time
from typing import Optional
from sqlalchemy import (
    String, Integer, Boolean, DateTime, Date, Time, Enum as SAEnum,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base
from models.driver import City


class TimeBlock(str, enum.Enum):
    """4-hour time blocks covering 24 hours."""
    BLOCK_00_04 = "00:00-04:00"
    BLOCK_04_08 = "04:00-08:00"
    BLOCK_08_12 = "08:00-12:00"
    BLOCK_12_16 = "12:00-16:00"
    BLOCK_16_20 = "16:00-20:00"
    BLOCK_20_24 = "20:00-24:00"


class ShiftStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    NO_SHOW = "no_show"
    CANCELLED = "cancelled"


class DriverAvailability(Base):
    """Driver submits availability for a given week."""
    __tablename__ = "driver_availability"
    __table_args__ = (
        UniqueConstraint("driver_id", "week_start", "day_of_week", "time_block"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True)
    week_start: Mapped[date] = mapped_column(Date, index=True)  # Monday of that week
    day_of_week: Mapped[int] = mapped_column(Integer)  # 0=Mon … 6=Sun
    time_block: Mapped[TimeBlock] = mapped_column(SAEnum(TimeBlock))
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    driver: Mapped["Driver"] = relationship(back_populates="availabilities")


class Shift(Base):
    """A scheduled shift slot for a city/day/time block."""
    __tablename__ = "shifts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    city: Mapped[City] = mapped_column(SAEnum(City))
    shift_date: Mapped[date] = mapped_column(Date, index=True)
    time_block: Mapped[TimeBlock] = mapped_column(SAEnum(TimeBlock))
    required_drivers: Mapped[int] = mapped_column(Integer, default=2)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    assignments: Mapped[list["ShiftAssignment"]] = relationship(
        back_populates="shift", cascade="all, delete-orphan"
    )


class ShiftAssignment(Base):
    """Links a driver to a specific shift."""
    __tablename__ = "shift_assignments"
    __table_args__ = (
        UniqueConstraint("shift_id", "driver_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shift_id: Mapped[int] = mapped_column(ForeignKey("shifts.id"), index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True)
    status: Mapped[ShiftStatus] = mapped_column(
        SAEnum(ShiftStatus), default=ShiftStatus.SCHEDULED
    )
    notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    shift: Mapped["Shift"] = relationship(back_populates="assignments")
    driver: Mapped["Driver"] = relationship(back_populates="shift_assignments")
