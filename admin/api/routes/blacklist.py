from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
from ...db.database import get_db
from ...db.models import BlacklistEntry

router = APIRouter(prefix="/blacklist", tags=["blacklist"])


class BlacklistIn(BaseModel):
    entity_type: str          # phone/customer/driver/email
    entity_value: str
    reason: str
    expires_at: Optional[datetime] = None
    added_by: Optional[str] = "owner"


def _row(b: BlacklistEntry) -> dict:
    return {
        "id": b.id, "entity_type": b.entity_type, "entity_value": b.entity_value,
        "reason": b.reason,
        "expires_at": b.expires_at.isoformat() if b.expires_at else None,
        "added_by": b.added_by, "active": b.active,
        "created_at": b.created_at.isoformat() if b.created_at else None,
    }


@router.get("/")
def list_blacklist(entity_type: Optional[str] = None, active_only: bool = True,
                   db: Session = Depends(get_db)):
    q = db.query(BlacklistEntry)
    if entity_type: q = q.filter(BlacklistEntry.entity_type == entity_type)
    if active_only: q = q.filter(BlacklistEntry.active == True)  # noqa: E712
    return [_row(b) for b in q.order_by(BlacklistEntry.id.desc()).all()]


@router.post("/")
def add_blacklist(body: BlacklistIn, db: Session = Depends(get_db)):
    b = BlacklistEntry(**body.model_dump())
    db.add(b); db.commit(); db.refresh(b)
    return _row(b)


@router.get("/check")
def check_blacklist(entity_type: str, entity_value: str, db: Session = Depends(get_db)):
    """Used by customer agent + dispatch to gate bookings."""
    now = datetime.now(timezone.utc)
    hit = db.query(BlacklistEntry).filter(
        BlacklistEntry.entity_type == entity_type,
        BlacklistEntry.entity_value == entity_value,
        BlacklistEntry.active == True,  # noqa: E712
    ).first()
    if hit and (hit.expires_at is None or hit.expires_at > now):
        return {"blocked": True, "reason": hit.reason,
                "expires_at": hit.expires_at.isoformat() if hit.expires_at else None}
    return {"blocked": False}


@router.delete("/{bid}")
def remove_blacklist(bid: int, db: Session = Depends(get_db)):
    b = db.get(BlacklistEntry, bid)
    if not b: raise HTTPException(404, "Entry not found")
    b.active = False
    db.commit()
    return {"ok": True}
