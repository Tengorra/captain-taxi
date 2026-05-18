from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime, timezone
from ...db.database import get_db
from ...db.models import Receipt

router = APIRouter(prefix="/receipts", tags=["receipts"])


class ReceiptIn(BaseModel):
    trip_id: str
    customer_id: Optional[str] = None
    subtotal: float = 0.0
    tax: float = 0.0
    total: float = 0.0
    items_json: Optional[List[Any]] = None
    file_path: Optional[str] = None
    sent_to_email: Optional[str] = None


def _row(r: Receipt) -> dict:
    return {
        "id": r.id, "trip_id": r.trip_id, "customer_id": r.customer_id,
        "subtotal": r.subtotal, "tax": r.tax, "total": r.total,
        "items_json": r.items_json or [],
        "file_path": r.file_path, "sent_to_email": r.sent_to_email,
        "sent_at": r.sent_at.isoformat() if r.sent_at else None,
        "icabbi_ref": r.icabbi_ref,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


@router.get("/")
def list_receipts(trip_id: Optional[str] = None, customer_id: Optional[str] = None,
                  limit: int = 200, db: Session = Depends(get_db)):
    q = db.query(Receipt)
    if trip_id: q = q.filter(Receipt.trip_id == trip_id)
    if customer_id: q = q.filter(Receipt.customer_id == customer_id)
    return [_row(r) for r in q.order_by(Receipt.id.desc()).limit(limit).all()]


@router.post("/")
def create_receipt(body: ReceiptIn, db: Session = Depends(get_db)):
    r = Receipt(**body.model_dump())
    db.add(r); db.commit(); db.refresh(r)
    return _row(r)


@router.post("/{rid}/mark-sent")
def mark_sent(rid: int, db: Session = Depends(get_db)):
    r = db.get(Receipt, rid)
    if not r: raise HTTPException(404, "Receipt not found")
    r.sent_at = datetime.now(timezone.utc)
    db.commit()
    return _row(r)


@router.get("/{rid}")
def get_receipt(rid: int, db: Session = Depends(get_db)):
    r = db.get(Receipt, rid)
    if not r: raise HTTPException(404, "Receipt not found")
    return _row(r)
