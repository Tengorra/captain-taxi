"""
Corporate Account Invoicing Service
====================================
On the 1st of each month:
  1. Pull all completed trips tagged to corporate accounts for the prior month.
  2. Generate an invoice (PDF + QuickBooks).
  3. Email the invoice to the corporate contact.
  4. Track payment status; send reminder at 14 days, escalate at 30 days.
"""
import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO

from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from config import settings
from models.invoice import Invoice, InvoiceLineItem, InvoiceStatus, CorporateAccount
from models.trip import Trip, TripStatus
import services.quickbooks as qb_service
import services.notifications as notify
import utils.pdf as pdf_util

logger = logging.getLogger(__name__)
TWO_PLACES = Decimal("0.01")
GST_RATE = Decimal("0.05")


def _invoice_number(account: CorporateAccount, period_start: date) -> str:
    return f"CT-{account.id:04d}-{period_start.strftime('%Y%m')}"


def _prior_month_range(ref_date: date | None = None) -> tuple[date, date]:
    today = ref_date or date.today()
    first_of_this_month = today.replace(day=1)
    last_of_last_month = first_of_this_month - timedelta(days=1)
    first_of_last_month = last_of_last_month.replace(day=1)
    return first_of_last_month, last_of_last_month


def generate_monthly_invoices(db: Session, ref_date: date | None = None) -> list[Invoice]:
    """Called on the 1st of each month. Generates invoices for all active corporate accounts."""
    period_start, period_end = _prior_month_range(ref_date)
    logger.info("Generating corporate invoices for %s – %s", period_start, period_end)

    accounts = db.query(CorporateAccount).filter_by(active=True).all()
    created: list[Invoice] = []

    for account in accounts:
        # Skip if already invoiced this period
        existing = db.query(Invoice).filter_by(
            corporate_account_id=account.id,
            period_start=period_start,
        ).first()
        if existing:
            logger.info("Invoice already exists for %s (%s) — skipping", account.name, period_start)
            continue

        trips = (
            db.query(Trip)
            .filter(
                Trip.corporate_account_id == account.id,
                Trip.status == TripStatus.COMPLETED,
                func.date(Trip.completed_at) >= period_start,
                func.date(Trip.completed_at) <= period_end,
            )
            .order_by(Trip.completed_at)
            .all()
        )

        if not trips:
            logger.debug("No trips for %s in %s — skipping invoice", account.name, period_start)
            continue

        subtotal = sum(t.fare for t in trips) or Decimal("0.00")
        gst = (subtotal * GST_RATE).quantize(TWO_PLACES, ROUND_HALF_UP)
        total = subtotal + gst

        inv = Invoice(
            invoice_number=_invoice_number(account, period_start),
            corporate_account_id=account.id,
            period_start=period_start,
            period_end=period_end,
            subtotal=subtotal,
            gst_amount=gst,
            total=total,
            status=InvoiceStatus.DRAFT,
            issued_at=datetime.now(timezone.utc),
            due_date=date.today() + timedelta(days=30),
        )
        db.add(inv)
        db.flush()

        # Line items — one per trip
        for trip in trips:
            db.add(InvoiceLineItem(
                invoice_id=inv.id,
                trip_id=trip.id,
                description=f"Taxi — {trip.completed_at.strftime('%b %d')} — {trip.pickup_address or ''} → {trip.dropoff_address or ''}",
                quantity=1,
                unit_price=trip.fare,
                line_total=trip.fare,
            ))

        db.commit()

        # Ensure QB customer exists
        if not account.qb_customer_id:
            try:
                account.qb_customer_id = qb_service.ensure_corporate_customer(
                    db, name=account.name, email=account.billing_email
                )
                db.commit()
            except Exception as exc:
                logger.error("QB customer creation failed for %s: %s", account.name, exc)

        # Push to QB
        if account.qb_customer_id:
            try:
                line_items_payload = [
                    {"description": li.description, "amount": li.line_total}
                    for li in inv.line_items
                ]
                qb_id = qb_service.push_corporate_invoice(
                    db,
                    qb_customer_id=account.qb_customer_id,
                    invoice_number=inv.invoice_number,
                    line_items=line_items_payload,
                    gst_amount=gst,
                    due_date=inv.due_date.isoformat(),
                    period=f"{period_start} – {period_end}",
                )
                inv.qb_invoice_id = qb_id
            except Exception as exc:
                logger.error("QB invoice push failed for %s: %s", account.name, exc)

        # Generate PDF
        try:
            pdf_bytes = pdf_util.generate_invoice_pdf(inv, account)
            pdf_path = f"/var/captain-taxi/invoices/{inv.invoice_number}.pdf"
            with open(pdf_path, "wb") as f:
                f.write(pdf_bytes)
            inv.pdf_path = pdf_path
        except Exception as exc:
            logger.error("PDF generation failed for %s: %s", inv.invoice_number, exc)

        inv.status = InvoiceStatus.SENT
        db.commit()

        # Email invoice
        try:
            notify.email_invoice(
                to_email=account.billing_email,
                to_name=account.contact_name or account.name,
                invoice=inv,
                account=account,
                pdf_path=inv.pdf_path,
            )
        except Exception as exc:
            logger.error("Invoice email failed for %s: %s", account.name, exc)

        created.append(inv)
        logger.info("Invoice %s sent to %s — $%s", inv.invoice_number, account.billing_email, total)

    return created


def send_payment_reminders(db: Session) -> None:
    """
    Check all open invoices:
    - 14 days unpaid → send reminder
    - 30 days unpaid → escalate (notify owner + stronger email)
    Called daily by scheduler.
    """
    now = datetime.now(timezone.utc)
    today = date.today()

    open_invoices = (
        db.query(Invoice)
        .filter(Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.VIEWED]))
        .all()
    )

    for inv in open_invoices:
        if not inv.due_date:
            continue
        days_overdue = (today - inv.due_date).days
        account = inv.corporate_account

        if days_overdue >= settings.invoice_escalation_days and not inv.escalated_at:
            _escalate_invoice(db, inv, account, days_overdue)
        elif days_overdue >= settings.invoice_reminder_days and not inv.reminder_sent_at:
            _remind_invoice(db, inv, account, days_overdue)


def _remind_invoice(db: Session, inv: Invoice, account: CorporateAccount, days_overdue: int) -> None:
    logger.info("Sending 14-day reminder for invoice %s", inv.invoice_number)
    try:
        notify.email_invoice_reminder(
            to_email=account.billing_email,
            to_name=account.contact_name or account.name,
            invoice=inv,
            days_overdue=days_overdue,
            escalated=False,
        )
        inv.reminder_sent_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as exc:
        logger.error("Reminder email failed for %s: %s", inv.invoice_number, exc)


def _escalate_invoice(db: Session, inv: Invoice, account: CorporateAccount, days_overdue: int) -> None:
    logger.warning("Escalating overdue invoice %s (%d days)", inv.invoice_number, days_overdue)
    try:
        # Strong reminder to client
        notify.email_invoice_reminder(
            to_email=account.billing_email,
            to_name=account.contact_name or account.name,
            invoice=inv,
            days_overdue=days_overdue,
            escalated=True,
        )
        # Notify owner
        notify.email_owner(
            subject=f"OVERDUE INVOICE — {account.name} — {days_overdue} days",
            body=(
                f"Invoice {inv.invoice_number} for {account.name} is {days_overdue} days overdue.\n"
                f"Amount: ${inv.total:.2f}\n"
                f"Contact: {account.billing_email}\n\n"
                "Consider suspending account service until payment is received."
            ),
        )
        inv.escalated_at = datetime.now(timezone.utc)
        inv.status = InvoiceStatus.OVERDUE
        db.commit()
    except Exception as exc:
        logger.error("Escalation failed for %s: %s", inv.invoice_number, exc)
