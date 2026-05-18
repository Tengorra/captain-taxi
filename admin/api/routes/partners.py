from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from ...db.database import get_db
from ...db.models import Partner

router = APIRouter(prefix="/partners", tags=["partners"])


class PartnerIn(BaseModel):
    name: str
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    city: Optional[str] = None
    commission_rate: float = 0.10
    active: bool = True
    notes: Optional[str] = None


def _row(p: Partner) -> dict:
    return {
        "id": p.id, "name": p.name, "contact_name": p.contact_name,
        "contact_phone": p.contact_phone, "contact_email": p.contact_email,
        "city": p.city, "commission_rate": p.commission_rate,
        "active": p.active, "notes": p.notes, "icabbi_ref": p.icabbi_ref,
    }


@router.get("/")
def list_partners(active: Optional[bool] = None, db: Session = Depends(get_db)):
    q = db.query(Partner)
    if active is not None: q = q.filter(Partner.active == active)
    return [_row(p) for p in q.order_by(Partner.name.asc()).all()]


@router.post("/")
def create_partner(body: PartnerIn, db: Session = Depends(get_db)):
    p = Partner(**body.model_dump())
    db.add(p); db.commit(); db.refresh(p)
    return _row(p)


@router.patch("/{pid}")
def update_partner(pid: int, body: PartnerIn, db: Session = Depends(get_db)):
    p = db.get(Partner, pid)
    if not p: raise HTTPException(404, "Partner not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit(); db.refresh(p)
    return _row(p)


@router.delete("/{pid}")
def delete_partner(pid: int, db: Session = Depends(get_db)):
    p = db.get(Partner, pid)
    if not p: raise HTTPException(404, "Partner not found")
    db.delete(p); db.commit()
    return {"ok": True}
