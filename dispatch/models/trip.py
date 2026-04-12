import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Float, DateTime, Enum, Text, Integer, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class TripStatus(str, enum.Enum):
    pending = "pending"
    assigned = "assigned"
    en_route = "en_route"
    arrived = "arrived"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"
    noshow = "noshow"


class TripPriority(int, enum.Enum):
    normal = 0
    high = 1
    urgent = 2


class BookingSource(str, enum.Enum):
    phone = "phone"
    app = "app"
    web = "web"
    whatsapp = "whatsapp"
    agent = "agent"


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # Customer info
    customer_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    customer_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    customer_email: Mapped[str] = mapped_column(String(200), nullable=False, default="")

    # Pickup
    pickup_address: Mapped[str] = mapped_column(String(300), nullable=False)
    pickup_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    pickup_lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Dropoff
    dropoff_address: Mapped[str] = mapped_column(String(300), nullable=False)
    dropoff_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    dropoff_lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    city: Mapped[str] = mapped_column(String(20), nullable=False)
    via_address: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    instructions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    site: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fare_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    fare_final: Mapped[float | None] = mapped_column(Float, nullable=True)

    status: Mapped[TripStatus] = mapped_column(
        Enum(TripStatus), nullable=False, default=TripStatus.pending
    )
    booking_source: Mapped[BookingSource] = mapped_column(
        Enum(BookingSource), nullable=False, default=BookingSource.agent
    )

    # Assignment
    driver_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("drivers.id"), nullable=True
    )
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    assignment_attempts: Mapped[int] = mapped_column(nullable=False, default=0)
    ai_reasoning: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Lifecycle timestamps
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    driver_en_route_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    driver_arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pickup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    noshow_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Scheduled pickup (for pre-bookings)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    driver = relationship("Driver", back_populates="trips", foreign_keys=[driver_id])

    def __repr__(self) -> str:
        return f"<Trip {self.id[:8]} [{self.status}] {self.pickup_address[:30]}>"
