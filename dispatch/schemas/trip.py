from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator
from models.trip import TripStatus, BookingSource, TripPriority


class TripCreate(BaseModel):
    customer_name: str = ""
    customer_phone: str
    customer_email: str = ""
    pickup_address: str
    pickup_lat: Optional[float] = None
    pickup_lng: Optional[float] = None
    dropoff_address: str
    dropoff_lat: Optional[float] = None
    dropoff_lng: Optional[float] = None
    via_address: str = ""
    city: str
    notes: str = ""
    instructions: str = ""
    site: str = ""
    priority: int = 0
    fare_estimate: Optional[float] = None
    booking_source: BookingSource = BookingSource.agent
    scheduled_for: Optional[datetime] = None

    @field_validator("city")
    @classmethod
    def validate_city(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in ("saskatoon", "regina"):
            raise ValueError("city must be 'saskatoon' or 'regina'")
        return v


class TripUpdate(BaseModel):
    pickup_address: Optional[str] = None
    pickup_lat: Optional[float] = None
    pickup_lng: Optional[float] = None
    dropoff_address: Optional[str] = None
    dropoff_lat: Optional[float] = None
    dropoff_lng: Optional[float] = None
    via_address: Optional[str] = None
    notes: Optional[str] = None
    instructions: Optional[str] = None
    site: Optional[str] = None
    priority: Optional[int] = None
    fare_estimate: Optional[float] = None
    fare_final: Optional[float] = None
    scheduled_for: Optional[datetime] = None


class TripCancelRequest(BaseModel):
    reason: str = ""


class TripReassignRequest(BaseModel):
    driver_id: str
    reason: str = ""


class TripResponse(BaseModel):
    id: str
    customer_name: str
    customer_phone: str
    customer_email: str
    pickup_address: str
    pickup_lat: Optional[float]
    pickup_lng: Optional[float]
    dropoff_address: str
    dropoff_lat: Optional[float]
    dropoff_lng: Optional[float]
    via_address: str
    city: str
    notes: str
    instructions: str
    site: str
    priority: int
    fare_estimate: Optional[float]
    fare_final: Optional[float]
    status: TripStatus
    booking_source: BookingSource
    driver_id: Optional[str]
    assigned_at: Optional[datetime]
    assignment_attempts: int
    ai_reasoning: str
    requested_at: datetime
    driver_en_route_at: Optional[datetime]
    driver_arrived_at: Optional[datetime]
    pickup_at: Optional[datetime]
    completed_at: Optional[datetime]
    cancelled_at: Optional[datetime]
    cancellation_reason: str
    noshow_at: Optional[datetime]
    scheduled_for: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}
