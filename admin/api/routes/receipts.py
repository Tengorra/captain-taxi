import io
import os
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime, timezone
from ...db.database import get_db
from ...db.models import Receipt, Trip, Item
from ...services.pdf_service import generate_receipt_pdf

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/receipts", tags=["receipts"])

GST_RATE = 0.05  # SK has 5% federal GST, no PST on most services
RECEIPTS_DIR = os.getenv("RECEIPTS_DIR", "/tmp/captain-taxi/receipts")


def _write_pdf(receipt: Receipt, trip: Optional[Trip]) -> Optional[str]:
    """Render PDF, save to disk, return path. Errors are logged + swallowed
    so a PDF failure never blocks the receipt row from being saved."""
    try:
        os.makedirs(RECEIPTS_DIR, exist_ok=True)
        pdf_bytes = generate_receipt_pdf(receipt, trip)
        path = os.path.join(RECEIPTS_DIR, f"receipt-{receipt.id}.pdf")
        with open(path, "wb") as f:
            f.write(pdf_bytes)
        return path
    except Exception as e:
        logger.warning("Receipt PDF generation failed for %s: %s", receipt.id, e)
        return None


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
    """Auto-snapshot a trip + extras catalogue items into a Receipt row,
    generate the PDF, and persist its path on the Receipt.
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

    path = _write_pdf(r, trip)
    if path:
        r.file_path = path
        db.commit(); db.refresh(r)
    return _row(r)


@router.get("/{rid}/pdf")
def download_receipt_pdf(rid: int, db: Session = Depends(get_db)):
    """Stream the receipt PDF. Regenerates on the fly if file_path is missing."""
    r = db.get(Receipt, rid)
    if not r:
        raise HTTPException(404, "Receipt not found")
    trip = db.get(Trip, r.trip_id) if r.trip_id else None

    if r.file_path and os.path.exists(r.file_path):
        with open(r.file_path, "rb") as f:
            pdf_bytes = f.read()
    else:
        pdf_bytes = generate_receipt_pdf(r, trip)
        # Persist for next time.
        path = _write_pdf(r, trip)
        if path:
            r.file_path = path
            db.commit()

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="receipt-{rid}.pdf"'},
    )


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
