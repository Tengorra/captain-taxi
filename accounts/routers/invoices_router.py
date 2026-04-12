"""Corporate invoicing endpoints."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import get_db
from models.invoice import Invoice, InvoiceStatus, CorporateAccount
import services.invoicing as inv_service

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.post("/generate-monthly")
def generate_monthly(ref_date: Optional[date] = Query(None), db: Session = Depends(get_db)):
    """Manually trigger monthly invoice generation."""
    invoices = inv_service.generate_monthly_invoices(db, ref_date=ref_date)
    return {
        "generated": len(invoices),
        "invoices": [
            {
                "invoice_number": i.invoice_number,
                "account": i.corporate_account.name,
                "total": float(i.total),
                "status": i.status,
                "qb_invoice_id": i.qb_invoice_id,
            }
            for i in invoices
        ],
    }


@router.get("/")
def list_invoices(
    status: Optional[InvoiceStatus] = Query(None),
    account_id: Optional[int] = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(Invoice)
    if status:
        q = q.filter_by(status=status)
    if account_id:
        q = q.filter_by(corporate_account_id=account_id)
    invoices = q.order_by(Invoice.issued_at.desc()).limit(limit).all()
    return [
        {
            "id": i.id,
            "invoice_number": i.invoice_number,
            "account": i.corporate_account.name,
            "period": f"{i.period_start} – {i.period_end}",
            "total": float(i.total),
            "status": i.status,
            "due_date": str(i.due_date),
            "paid_at": str(i.paid_at) if i.paid_at else None,
        }
        for i in invoices
    ]


@router.get("/{invoice_id}/pdf")
def download_invoice_pdf(invoice_id: int, db: Session = Depends(get_db)):
    inv = db.query(Invoice).get(invoice_id)
    if not inv:
        raise HTTPException(404, "Invoice not found")
    if not inv.pdf_path:
        raise HTTPException(404, "PDF not yet generated")
    return FileResponse(inv.pdf_path, media_type="application/pdf", filename=f"{inv.invoice_number}.pdf")


@router.post("/{invoice_id}/mark-paid")
def mark_paid(invoice_id: int, db: Session = Depends(get_db)):
    from datetime import datetime, timezone
    inv = db.query(Invoice).get(invoice_id)
    if not inv:
        raise HTTPException(404, "Invoice not found")
    inv.status = InvoiceStatus.PAID
    inv.paid_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "paid", "invoice_number": inv.invoice_number}


@router.post("/run-reminders")
def run_reminders(db: Session = Depends(get_db)):
    """Manually trigger payment reminder checks."""
    inv_service.send_payment_reminders(db)
    return {"status": "done"}


# ─── Corporate Accounts CRUD ──────────────────────────────────────────────────

@router.get("/accounts/")
def list_accounts(db: Session = Depends(get_db)):
    accounts = db.query(CorporateAccount).filter_by(active=True).all()
    return [
        {"id": a.id, "name": a.name, "city": a.city, "billing_email": a.billing_email, "contact": a.contact_name}
        for a in accounts
    ]


@router.post("/accounts/")
def create_account(
    name: str,
    billing_email: str,
    city: str = "Saskatoon",
    contact_name: Optional[str] = None,
    contact_phone: Optional[str] = None,
    address: Optional[str] = None,
    db: Session = Depends(get_db),
):
    account = CorporateAccount(
        name=name,
        billing_email=billing_email,
        city=city,
        contact_name=contact_name,
        contact_phone=contact_phone,
        address=address,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return {"id": account.id, "name": account.name, "status": "created"}
