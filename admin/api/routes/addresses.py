from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from ...db.database import get_db
from ...db.models import Address

router = APIRouter(prefix="/addresses", tags=["addresses"])


class AddressIn(BaseModel):
    label: Optional[str] = None
    line1: str
    line2: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = "SK"
    postal: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    address_type: Optional[str] = "other"
    customer_id: Optional[str] = None
    notes: Optional[str] = None


def _row(a: Address) -> dict:
    return {
        "id": a.id, "label": a.label, "line1": a.line1, "line2": a.line2,
        "city": a.city, "province": a.province, "postal": a.postal,
        "lat": a.lat, "lng": a.lng, "address_type": a.address_type,
        "customer_id": a.customer_id, "notes": a.notes,
        "icabbi_ref": a.icabbi_ref,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@router.get("/")
def list_addresses(customer_id: Optional[str] = None, search: Optional[str] = None,
                   limit: int = 200, db: Session = Depends(get_db)):
    q = db.query(Address)
    if customer_id:
        q = q.filter(Address.customer_id == customer_id)
    if search:
        like = f"%{search}%"
        q = q.filter((Address.line1.ilike(like)) | (Address.label.ilike(like)))
    return [_row(a) for a in q.order_by(Address.id.desc()).limit(limit).all()]


@router.post("/")
def create_address(body: AddressIn, db: Session = Depends(get_db)):
    a = Address(**body.model_dump())
    db.add(a); db.commit(); db.refresh(a)
    return _row(a)


@router.get("/{aid}")
def get_address(aid: int, db: Session = Depends(get_db)):
    a = db.get(Address, aid)
    if not a: raise HTTPException(404, "Address not found")
    return _row(a)


@router.patch("/{aid}")
def update_address(aid: int, body: AddressIn, db: Session = Depends(get_db)):
    a = db.get(Address, aid)
    if not a: raise HTTPException(404, "Address not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(a, k, v)
    db.commit(); db.refresh(a)
    return _row(a)


@router.delete("/{aid}")
def delete_address(aid: int, db: Session = Depends(get_db)):
    a = db.get(Address, aid)
    if not a: raise HTTPException(404, "Address not found")
    db.delete(a); db.commit()
    return {"ok": True}
