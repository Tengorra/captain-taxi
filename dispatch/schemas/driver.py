from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator
from models.driver import DriverStatus


class DriverCreate(BaseModel):
    name: str
    phone: str
    vehicle_plate: str
    vehicle_model: str = ""
    city: str
    status: Optional[DriverStatus] = None
    is_active: Optional[bool] = None
    rating: Optional[float] = None

    @field_validator("city")
    @classmethod
    def validate_city(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in ("saskatoon", "regina"):
            raise ValueError("city must be 'saskatoon' or 'regina'")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        digits = "".join(c for c in v if c.isdigit() or c == "+")
        if len(digits) < 10:
            raise ValueError("phone number too short")
        return v


class DriverUpdate(BaseModel):
    name: Optional[str] = None
    vehicle_plate: Optional[str] = None
    vehicle_model: Optional[str] = None
    city: Optional[str] = None
    is_active: Optional[bool] = None


class DriverResponse(BaseModel):
    id: str
    name: str
    phone: str
    vehicle_plate: str
    vehicle_model: str
    city: str
    status: DriverStatus
    rating: float
    total_trips: int
    is_active: bool
    last_lat: Optional[float]
    last_lng: Optional[float]
    last_location_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class DriverStatusUpdate(BaseModel):
    status: DriverStatus


class DriverLocationUpdate(BaseModel):
    lat: float
    lng: float
    speed_kmh: Optional[float] = None
    heading: Optional[float] = None
    trip_id: Optional[str] = None

    @field_validator("lat")
    @classmethod
    def validate_lat(cls, v: float) -> float:
        if not (-90 <= v <= 90):
            raise ValueError("lat must be between -90 and 90")
        return v

    @field_validator("lng")
    @classmethod
    def validate_lng(cls, v: float) -> float:
        if not (-180 <= v <= 180):
            raise ValueError("lng must be between -180 and 180")
        return v
