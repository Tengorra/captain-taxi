from datetime import datetime
from decimal import Decimal
from sqlalchemy import Integer, String, Numeric, DateTime, Boolean, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from database import Base


class DriverStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)  # iCabbi driver ID

    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(50), default="Saskatoon")

    # Contractor info (for T4A)
    sin: Mapped[str | None] = mapped_column(String(20))  # Social Insurance Number — store encrypted in prod
    business_name: Mapped[str | None] = mapped_column(String(200))

    # Commission override (falls back to settings.driver_commission_rate if null)
    commission_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))

    status: Mapped[DriverStatus] = mapped_column(SAEnum(DriverStatus), default=DriverStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    # QB vendor ID for contractor payments
    qb_vendor_id: Mapped[str | None] = mapped_column(String(100))

    # Relationships
    trips: Mapped[list["Trip"]] = relationship("Trip", back_populates="driver")
    payments: Mapped[list["DriverPayment"]] = relationship("DriverPayment", back_populates="driver")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
