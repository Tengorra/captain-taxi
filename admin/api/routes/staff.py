from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel
from typing import Optional
from ...db.database import get_db
from ...db.models import Staff

router = APIRouter(prefix="/staff", tags=["staff"])

ROLES = {"owner", "admin", "viewer"}


class StaffIn(BaseModel):
    email: str
    name: str
    phone: Optional[str] = None
    role: str = "viewer"
    is_active: bool = True


def _row(s: Staff) -> dict:
    return {
        "id": s.id, "email": s.email, "name": s.name, "phone": s.phone,
        "role": s.role, "is_active": s.is_active,
        "last_login_at": s.last_login_at.isoformat() if s.last_login_at else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.get("/")
def list_staff(db: Session = Depends(get_db)):
    return [_row(s) for s in db.query(Staff).order_by(Staff.id.asc()).all()]


@router.post("/")
def create_staff(body: StaffIn, db: Session = Depends(get_db)):
    if body.role not in ROLES:
        raise HTTPException(400, f"role must be one of {sorted(ROLES)}")
    s = Staff(**body.model_dump())
    db.add(s)
    try:
        db.commit(); db.refresh(s)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"Email '{body.email}' already exists")
    return _row(s)


@router.patch("/{sid}")
def update_staff(sid: int, body: StaffIn, db: Session = Depends(get_db)):
    s = db.get(Staff, sid)
    if not s: raise HTTPException(404, "Staff not found")
    data = body.model_dump(exclude_unset=True)
    if "role" in data and data["role"] not in ROLES:
        raise HTTPException(400, f"role must be one of {sorted(ROLES)}")
    for k, v in data.items():
        setattr(s, k, v)
    db.commit(); db.refresh(s)
    return _row(s)


@router.delete("/{sid}")
def delete_staff(sid: int, db: Session = Depends(get_db)):
    s = db.get(Staff, sid)
    if not s: raise HTTPException(404, "Staff not found")
    db.delete(s); db.commit()
    return {"ok": True}
