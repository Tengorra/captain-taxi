import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Float, DateTime, Enum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class DriverStatus(str, enum.Enum):
    online = "online"
    offline = "offline"
    on_trip = "on_trip"
    break_ = "break"
    parked = "parked"      # Waiting at a rank/parking spot
    dropping = "dropping"  # Dropping off current passenger, nearly free
    bidding = "bidding"    # In bidding mode for a job


class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    vehicle_plate: Mapped[str] = mapped_column(String(20), nullable=False)
    vehicle_model: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    city: Mapped[str] = mapped_column(String(20), nullable=False)  # saskatoon | regina
    status: Mapped[DriverStatus] = mapped_column(
        Enum(DriverStatus), nullable=False, default=DriverStatus.offline
    )
    rating: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)
    total_trips: Mapped[int] = mapped_column(nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)

    # Last known GPS (also cached in Redis, this is the DB copy)
    last_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_location_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    trips = relationship("Trip", back_populates="driver", foreign_keys="Trip.driver_id")
    location_history = relationship("LocationHistory", back_populates="driver")

    def __repr__(self) -> str:
        return f"<Driver {self.name} [{self.status}]>"
