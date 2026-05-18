from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime, timezone
from ...db.database import get_db
from ...db.models import OwnerStatement
from ...services.owner_statements_service import (
    generate_for_period, generate_for_last_month,
)

router = APIRouter(prefix="/owner-statements", tags=["owner-statements"])


class GenerateIn(BaseModel):
    period_start: Optional[date] = None
    period_end: Optional[date] = None


class StatementIn(BaseModel):
    owner_name: str
    owner_email: Optional[str] = None
    vehicle_ref: Optional[str] = None
    period_start: date
    period_end: date
    gross: float = 0.0
    deductions: float = 0.0
    net: float = 0.0
    status: Optional[str] = "draft"
    pdf_path: Optional[str] = None
    notes: Optional[str] = None


def _row(s: OwnerStatement) -> dict:
    return {
        "id": s.id, "owner_name": s.owner_name, "owner_email": s.owner_email,
        "vehicle_ref": s.vehicle_ref,
        "period_start": s.period_start.isoformat() if s.period_start else None,
        "period_end": s.period_end.isoformat() if s.period_end else None,
        "gross": s.gross, "deductions": s.deductions, "net": s.net,
        "status": s.status, "pdf_path": s.pdf_path, "notes": s.notes,
        "sent_at": s.sent_at.isoformat() if s.sent_at else None,
        "paid_at": s.paid_at.isoformat() if s.paid_at else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.get("/")
def list_statements(status: Optional[str] = None, vehicle_ref: Optional[str] = None,
                    db: Session = Depends(get_db)):
    q = db.query(OwnerStatement)
    if status: q = q.filter(OwnerStatement.status == status)
    if vehicle_ref: q = q.filter(OwnerStatement.vehicle_ref == vehicle_ref)
    return [_row(s) for s in q.order_by(OwnerStatement.id.desc()).all()]


@router.post("/")
def create_statement(body: StatementIn, db: Session = Depends(get_db)):
    data = body.model_dump()
    if not data.get("net"):
        data["net"] = (data.get("gross") or 0) - (data.get("deductions") or 0)
    s = OwnerStatement(**data)
    db.add(s); db.commit(); db.refresh(s)
    return _row(s)


@router.post("/{sid}/mark-sent")
def mark_sent(sid: int, db: Session = Depends(get_db)):
    s = db.get(OwnerStatement, sid)
    if not s: raise HTTPException(404, "Statement not found")
    s.status = "sent"; s.sent_at = datetime.now(timezone.utc)
    db.commit()
    return _row(s)


@router.post("/{sid}/mark-paid")
def mark_paid(sid: int, db: Session = Depends(get_db)):
    s = db.get(OwnerStatement, sid)
    if not s: raise HTTPException(404, "Statement not found")
    s.status = "paid"; s.paid_at = datetime.now(timezone.utc)
    db.commit()
    return _row(s)


@router.post("/generate")
def generate(body: GenerateIn):
    """Roll up completed trips for a period into draft statements per
    vehicle_ref. Omit body to generate for the previous calendar month."""
    if body.period_start and body.period_end:
        if body.period_end < body.period_start:
            raise HTTPException(400, "period_end must be on/after period_start")
        return generate_for_period(body.period_start, body.period_end)
    return generate_for_last_month()
