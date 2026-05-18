from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime, timezone
from ...db.database import get_db
from ...db.models import Receipt, Trip, Item

router = APIRouter(prefix="/receipts", tags=["receipts"])

GST_RATE = 0.05  # SK has 5% federal GST, no PST on most services


class ReceiptIn(BaseModel):
    trip_id: str
    customer_id: Optional[str] = None
    subtotal: float = 0.0
    tax: float = 0.0
    total: float = 0.0
    items_json: Optional[List[Any]] = None
    file_path: Optional[str] = None
    sent_to_email: Optional[str] = None


class ReceiptFromTripIn(BaseModel):
    trip_id: str
    item_codes: Optional[List[str]] = None     # extras catalogue codes to attach
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


@router.post("/from-trip")
def create_receipt_from_trip(body: ReceiptFromTripIn, db: Session = Depends(get_db)):
    """Auto-snapshot a trip + extras catalogue items into a Receipt row.
    Returns 409 if a receipt already exists for the trip."""
    trip = db.get(Trip, body.trip_id)
    if not trip:
        raise HTTPException(404, f"Trip {body.trip_id} not found")
    if db.query(Receipt).filter(Receipt.trip_id == body.trip_id).first():
        raise HTTPException(409, f"Receipt already exists for trip {body.trip_id}")

    items_snapshot: list[dict] = []
    extras_total = 0.0
    taxable_extras = 0.0
    if body.item_codes:
        items = db.query(Item).filter(Item.code.in_(body.item_codes), Item.active == True).all()  # noqa: E712
        for it in items:
            line = {"code": it.code, "name": it.name, "price": it.price, "taxable": it.taxable}
            items_snapshot.append(line)
            extras_total += it.price or 0.0
            if it.taxable:
                taxable_extras += it.price or 0.0

    fare = trip.fare or 0.0
    subtotal = round(fare + extras_total, 2)
    # Trip fare is treated as taxable; non-taxable Items are excluded from GST base.
    tax = round((fare + taxable_extras) * GST_RATE, 2)
    total = round(subtotal + tax, 2)

    r = Receipt(
        trip_id=trip.id,
        customer_id=trip.customer_id,
        subtotal=subtotal,
        tax=tax,
        total=total,
        items_json=items_snapshot,
        sent_to_email=body.sent_to_email,
    )
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
