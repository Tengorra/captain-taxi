import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Boolean, DateTime, Text, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class SuspensionReason(str, enum.Enum):
    PERFORMANCE = "performance"
    COMPLAINT = "complaint"
    COMPLIANCE = "compliance"
    INVESTIGATION = "investigation"
    OTHER = "other"


class TerminationReason(str, enum.Enum):
    PERFORMANCE = "performance"
    MISCONDUCT = "misconduct"
    COMPLIANCE = "compliance"
    VOLUNTARY = "voluntary"
    OTHER = "other"


class DriverSuspension(Base):
    __tablename__ = "driver_suspensions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True)
    reason: Mapped[SuspensionReason] = mapped_column(SAEnum(SuspensionReason))
    detail: Mapped[Optional[str]] = mapped_column(Text)
    suspended_by: Mapped[str] = mapped_column(String(100))  # "agent" or "owner"
    lifted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    lifted_by: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    driver: Mapped["Driver"] = relationship(back_populates="suspensions")


class DriverTermination(Base):
    __tablename__ = "driver_terminations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True, unique=True)
    reason: Mapped[TerminationReason] = mapped_column(SAEnum(TerminationReason))
    detail: Mapped[Optional[str]] = mapped_column(Text)
    termination_letter: Mapped[Optional[str]] = mapped_column(Text)  # generated letter
    owner_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    owner_approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    effective_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    driver: Mapped["Driver"] = relationship(back_populates="termination")
