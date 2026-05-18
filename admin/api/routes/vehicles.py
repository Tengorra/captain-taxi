"""Vehicle CRUD + iCabbi vehicle-dump import.

iCabbi exports a vehicle dump with columns like:
    Vehicle Ref, AKA, Internal System ID, Make, Model, Colour, Registration,
    PLATE, Active, NCT/MOT Expiry, Plate Expiry, Insurer, Insurance,
    Insurance Expiry, Year, Credit Card Payments, Wi-Fi, Comments,
    Road Tax Expiry, Council Compliance Expiry, Hire Expiry, Owner Driver,
    Updated, Deleted, Device Identifier, Sensors, Payment Device,
    Payment Version, Light Control, Status Control, Vehicle Phone,
    Co2 Emission, Wheelchair, Saloon, Executive, Good Condition,
    Average Condition, 4 Seater, 5 Seater, …, Estate, High Rider, SEDAN,
    MINIVAN, SUV.

Rows are de-duplicated by `vehicle_ref` (NOT `plate`, because iCabbi keeps
"82" and "82_Old" as separate rows for the same physical plate)."""
import uuid
from datetime import datetime, date
from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ...db.database import get_db
from ...db.models import Vehicle, Driver


router = APIRouter(prefix="/vehicles", tags=["vehicles"])


class VehicleCreate(BaseModel):
    vehicle_ref: Optional[str] = None
    aka: Optional[str] = None
    internal_system_id: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    color: Optional[str] = None
    registration: Optional[str] = None
    plate: Optional[str] = None
    year: Optional[int] = None
    city: Optional[str] = None
    is_active: Optional[bool] = None
    is_deleted: Optional[bool] = None
    comments: Optional[str] = None

    # Expiries (accept ISO date or datetime — iCabbi exports MM/DD/YYYY HH:mm
    # which the dashboard normalises before posting)
    nct_mot_expiry: Optional[str] = None
    plate_expiry: Optional[str] = None
    insurance_expiry: Optional[str] = None
    road_tax_expiry: Optional[str] = None
    council_compliance_expiry: Optional[str] = None
    hire_expiry: Optional[str] = None

    insurer: Optional[str] = None
    insurance: Optional[str] = None
    owner_driver: Optional[bool] = None
    device_identifier: Optional[str] = None
    sensors: Optional[str] = None
    payment_device: Optional[str] = None
    payment_version: Optional[str] = None
    light_control: Optional[str] = None
    status_control: Optional[str] = None
    vehicle_phone: Optional[str] = None
    co2_emission: Optional[float] = None

    credit_card_payments: Optional[bool] = None
    wifi: Optional[bool] = None
    wheelchair: Optional[bool] = None
    saloon: Optional[bool] = None
    executive: Optional[bool] = None
    good_condition: Optional[bool] = None
    average_condition: Optional[bool] = None
    seater_4: Optional[bool] = None
    seater_5: Optional[bool] = None
    seater_6: Optional[bool] = None
    seater_7: Optional[bool] = None
    seater_8: Optional[bool] = None
    body_low_rider: Optional[bool] = None
    body_estate: Optional[bool] = None
    body_high_rider: Optional[bool] = None
    body_sedan: Optional[bool] = None
    body_minivan: Optional[bool] = None
    body_suv: Optional[bool] = None

    driver_id: Optional[str] = None       # explicit FK
    driver_vehicle_ref: Optional[str] = None  # link by iCabbi vehicle_ref on driver


def _parse_dt(val: Optional[str]) -> Optional[datetime]:
    if not val:
        return None
    try:
        return datetime.fromisoformat(val.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        pass
    try:
        return datetime.strptime(val[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def _parse_d(val: Optional[str]) -> Optional[date]:
    dt = _parse_dt(val)
    return dt.date() if dt else None


@router.post("/")
def create_vehicle(body: VehicleCreate, db: Session = Depends(get_db)):
    # De-dupe by vehicle_ref (iCabbi REF), not plate.
    if body.vehicle_ref:
        existing = db.query(Vehicle).filter(Vehicle.vehicle_ref == body.vehicle_ref).first()
        if existing:
            raise HTTPException(409, f"Vehicle with ref {body.vehicle_ref} already exists")

    # Best-effort driver linkage by vehicle_ref on the driver.
    driver_id = body.driver_id
    if not driver_id and body.driver_vehicle_ref:
        d = db.query(Driver).filter(Driver.vehicle_ref == body.driver_vehicle_ref).first()
        if d:
            driver_id = d.id

    vehicle = Vehicle(
        id=str(uuid.uuid4()),
        vehicle_ref=body.vehicle_ref,
        aka=body.aka,
        internal_system_id=body.internal_system_id,
        plate=(body.plate or body.registration or "").strip().upper() or None,
        registration=body.registration,
        make=body.make,
        model=body.model,
        color=body.color,
        year=body.year,
        city=body.city,
        is_active=bool(body.is_active) if body.is_active is not None else True,
        is_deleted=bool(body.is_deleted) if body.is_deleted is not None else False,
        comments=body.comments,
        nct_mot_expiry=_parse_dt(body.nct_mot_expiry),
        plate_expiry=_parse_dt(body.plate_expiry),
        insurance_expiry=_parse_d(body.insurance_expiry),
        road_tax_expiry=_parse_dt(body.road_tax_expiry),
        council_compliance_expiry=_parse_dt(body.council_compliance_expiry),
        hire_expiry=_parse_dt(body.hire_expiry),
        insurer=body.insurer,
        insurance=body.insurance,
        owner_driver=bool(body.owner_driver) if body.owner_driver is not None else False,
        device_identifier=body.device_identifier,
        sensors=body.sensors,
        payment_device=body.payment_device,
        payment_version=body.payment_version,
        light_control=body.light_control,
        status_control=body.status_control,
        vehicle_phone=body.vehicle_phone,
        co2_emission=body.co2_emission,
        credit_card_payments=bool(body.credit_card_payments) if body.credit_card_payments is not None else False,
        wifi=bool(body.wifi) if body.wifi is not None else False,
        wheelchair=bool(body.wheelchair) if body.wheelchair is not None else False,
        saloon=bool(body.saloon) if body.saloon is not None else False,
        executive=bool(body.executive) if body.executive is not None else False,
        good_condition=bool(body.good_condition) if body.good_condition is not None else False,
        average_condition=bool(body.average_condition) if body.average_condition is not None else False,
        seater_4=bool(body.seater_4) if body.seater_4 is not None else False,
        seater_5=bool(body.seater_5) if body.seater_5 is not None else False,
        seater_6=bool(body.seater_6) if body.seater_6 is not None else False,
        seater_7=bool(body.seater_7) if body.seater_7 is not None else False,
        seater_8=bool(body.seater_8) if body.seater_8 is not None else False,
        body_low_rider=bool(body.body_low_rider) if body.body_low_rider is not None else False,
        body_estate=bool(body.body_estate) if body.body_estate is not None else False,
        body_high_rider=bool(body.body_high_rider) if body.body_high_rider is not None else False,
        body_sedan=bool(body.body_sedan) if body.body_sedan is not None else False,
        body_minivan=bool(body.body_minivan) if body.body_minivan is not None else False,
        body_suv=bool(body.body_suv) if body.body_suv is not None else False,
        driver_id=driver_id,
    )
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return _serialize(vehicle)


@router.get("/")
def list_vehicles(
    active: Optional[bool] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Vehicle)
    if active is not None:
        q = q.filter(Vehicle.is_active == active)
    if search:
        like = f"%{search}%"
        q = q.filter(
            (Vehicle.plate.ilike(like)) |
            (Vehicle.vehicle_ref.ilike(like)) |
            (Vehicle.make.ilike(like)) |
            (Vehicle.model.ilike(like))
        )
    return [_serialize(v) for v in q.order_by(Vehicle.vehicle_ref).all()]


def _serialize(v: Vehicle) -> dict:
    return {
        "id": v.id,
        "vehicle_ref": v.vehicle_ref,
        "aka": v.aka,
        "plate": v.plate,
        "registration": v.registration,
        "make": v.make,
        "model": v.model,
        "color": v.color,
        "year": v.year,
        "city": v.city,
        "is_active": bool(v.is_active),
        "is_deleted": bool(v.is_deleted),
        "insurer": v.insurer,
        "insurance_expiry": v.insurance_expiry.isoformat() if v.insurance_expiry else None,
        "plate_expiry": v.plate_expiry.isoformat() if v.plate_expiry else None,
        "nct_mot_expiry": v.nct_mot_expiry.isoformat() if v.nct_mot_expiry else None,
        "hire_expiry": v.hire_expiry.isoformat() if v.hire_expiry else None,
        "council_compliance_expiry": v.council_compliance_expiry.isoformat() if v.council_compliance_expiry else None,
        "wheelchair": bool(v.wheelchair),
        "executive": bool(v.executive),
        "driver_id": v.driver_id,
    }
