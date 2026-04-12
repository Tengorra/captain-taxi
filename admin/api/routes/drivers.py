from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from ...db.database import get_db
from ...db.models import Driver, Vehicle, Trip

router = APIRouter(prefix="/drivers", tags=["drivers"])

# Status values used in actual DB (from drivers agent)
ONLINE_STATUSES = {"active", "on_trip", "available"}
SUSPENDED_STATUS = "suspended"


class DriverCreate(BaseModel):
    # Required
    name: str
    phone: str
    city: str
    # Personal
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    mobile_phone: Optional[str] = None
    other_phone: Optional[str] = None
    sex: Optional[str] = None
    aka: Optional[str] = None
    # Professional
    status: Optional[str] = "pending"
    driver_type: Optional[str] = "regular"
    # Licensing
    licence_number: Optional[str] = None
    licence_expiry: Optional[str] = None
    badge_number: Optional[str] = None
    badge_expiry: Optional[str] = None
    badge_type: Optional[str] = None
    tax_number: Optional[str] = None
    # Vehicle
    vehicle_model: Optional[str] = None
    vehicle_plate: Optional[str] = None
    # Payments
    commission_rate: Optional[float] = 0.30
    payment_on: Optional[str] = None
    payment_type: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    sort_code: Optional[str] = None
    notes: Optional[str] = None


class DriverUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    city: Optional[str] = None
    commission_rate: Optional[float] = None
    performance_score: Optional[float] = None
    notes: Optional[str] = None


class MessageBody(BaseModel):
    message: str


STATUS_MAP = {
    "pending":   "onboarding",
    "active":    "active",
    "offline":   "inactive",
    "inactive":  "inactive",
    "suspended": "suspended",
    "on_trip":   "active",
}


@router.post("/")
def create_driver(body: DriverCreate, db: Session = Depends(get_db)):
    # Build display name from first+last if full name not already set
    display_name = body.name.strip() or f"{body.first_name or ''} {body.last_name or ''}".strip()
    if not display_name:
        from fastapi import HTTPException
        raise HTTPException(400, "Driver name is required")

    driver = Driver(
        name=display_name,
        phone=body.phone,
        email=body.email,
        city=body.city,
        status=STATUS_MAP.get(body.status or "pending", "onboarding"),
        license_number=body.licence_number,
        license_expiry=body.licence_expiry,
        taxi_license_number=body.badge_number,
        taxi_license_expiry=body.badge_expiry,
        notes=body.notes,
    )
    db.add(driver)
    db.flush()  # get ID before creating vehicle

    if body.vehicle_plate:
        parts = (body.vehicle_model or "").split(" ", 1)
        vehicle = Vehicle(
            plate=body.vehicle_plate.upper().strip(),
            make=parts[0] if parts[0] else "Unknown",
            model=parts[1] if len(parts) > 1 else "",
            year=datetime.utcnow().year,
            driver_id=driver.id,
            city=body.city,
        )
        db.add(vehicle)

    db.commit()
    db.refresh(driver)
    return _driver_summary(driver, db)


@router.get("/")
def list_drivers(
    city: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    q = db.query(Driver)
    if city:
        q = q.filter(Driver.city == city)
    if status:
        q = q.filter(Driver.status == status)
    if search:
        q = q.filter(Driver.name.ilike(f"%{search}%"))
    drivers = q.order_by(Driver.name).all()
    return [_driver_summary(d, db) for d in drivers]


@router.get("/{driver_id}")
def get_driver(driver_id: str, db: Session = Depends(get_db)):
    driver = db.query(Driver).filter_by(id=driver_id).first()
    if not driver:
        raise HTTPException(404, "Driver not found")
    return _driver_detail(driver, db)


@router.patch("/{driver_id}")
def update_driver(driver_id: str, body: DriverUpdate, db: Session = Depends(get_db)):
    driver = db.query(Driver).filter_by(id=driver_id).first()
    if not driver:
        raise HTTPException(404, "Driver not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(driver, field, val)
    driver.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "driver": _driver_summary(driver, db)}


@router.post("/{driver_id}/suspend")
def suspend_driver(driver_id: str, db: Session = Depends(get_db)):
    driver = db.query(Driver).filter_by(id=driver_id).first()
    if not driver:
        raise HTTPException(404, "Driver not found")
    driver.status = SUSPENDED_STATUS
    driver.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "message": f"{driver.name} suspended"}


@router.post("/{driver_id}/activate")
def activate_driver(driver_id: str, db: Session = Depends(get_db)):
    driver = db.query(Driver).filter_by(id=driver_id).first()
    if not driver:
        raise HTTPException(404, "Driver not found")
    driver.status = "offline"
    driver.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "message": f"{driver.name} activated"}


@router.post("/{driver_id}/message")
def send_message(driver_id: str, body: MessageBody, db: Session = Depends(get_db)):
    driver = db.query(Driver).filter_by(id=driver_id).first()
    if not driver:
        raise HTTPException(404, "Driver not found")
    if not driver.phone:
        raise HTTPException(400, "Driver has no phone number")
    from ...services.twilio_service import send_sms
    sid = send_sms(driver.phone, body.message)
    return {"ok": True, "sid": sid}


@router.get("/{driver_id}/trips")
def get_driver_trips(driver_id: str, limit: int = 50, db: Session = Depends(get_db)):
    trips = (
        db.query(Trip)
        .filter(Trip.driver_id == driver_id)
        .order_by(Trip.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": t.id,
            "city": t.city,
            "status": t.status,
            "pickup": t.pickup_address,
            "dropoff": t.dropoff_address,
            "fare": t.fare or 0,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        }
        for t in trips
    ]


@router.get("/{driver_id}/documents")
def get_driver_documents(driver_id: str, db: Session = Depends(get_db)):
    from ...db.models import Document
    docs = db.query(Document).filter(
        Document.entity_id == driver_id,
        Document.entity_type == "driver"
    ).all()
    return [
        {
            "id": d.id,
            "type": d.doc_type,
            "status": d.status,
            "expiry_date": d.expiry_date.isoformat() if d.expiry_date else None,
            "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else None,
        }
        for d in docs
    ]


def _get_vehicle(driver_id: str, db: Session) -> Optional[Vehicle]:
    return db.query(Vehicle).filter(
        Vehicle.driver_id == driver_id,
        Vehicle.is_active == True
    ).first()


def _driver_summary(d: Driver, db: Session) -> dict:
    vehicle = _get_vehicle(d.id, db)
    return {
        "id": d.id,
        "name": d.name,
        "phone": d.phone,
        "city": d.city,
        "status": d.status,
        "performance_score": d.performance_score if d.performance_score is not None else 100.0,
        "commission_rate": d.commission_rate if d.commission_rate is not None else 0.30,
        "vehicle_plate": vehicle.plate if vehicle else None,
        "vehicle_model": f"{vehicle.make} {vehicle.model}" if vehicle else None,
    }


def _driver_detail(d: Driver, db: Session) -> dict:
    summary = _driver_summary(d, db)
    summary["email"] = d.email
    summary["notes"] = d.notes
    summary["created_at"] = d.created_at.isoformat() if d.created_at else None

    completed_trips = db.query(Trip).filter(
        Trip.driver_id == d.id,
        Trip.status == "completed"
    ).all()
    commission = d.commission_rate if d.commission_rate is not None else 0.30
    total_earnings = sum((t.fare or 0) for t in completed_trips) * (1 - commission)
    summary["total_trips"] = len(completed_trips)
    summary["total_earnings"] = round(total_earnings, 2)

    from ...db.models import Document
    docs = db.query(Document).filter(
        Document.entity_id == d.id,
        Document.entity_type == "driver"
    ).all()
    summary["documents"] = [
        {
            "type": doc.doc_type,
            "status": doc.status,
            "expiry_date": doc.expiry_date.isoformat() if doc.expiry_date else None,
        }
        for doc in docs
    ]
    return summary
