"""
Notifications Service
======================
Unified SMS (Twilio) and Email (SendGrid) for the accounts agent.
"""
import logging
from pathlib import Path

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Mail, Attachment, FileContent, FileName, FileType, Disposition, ContentId
)
from twilio.rest import Client as TwilioClient
import base64

from config import settings

logger = logging.getLogger(__name__)

_twilio: TwilioClient | None = None
_sg: SendGridAPIClient | None = None


def _get_twilio() -> TwilioClient:
    global _twilio
    if _twilio is None:
        _twilio = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)
    return _twilio


def _get_sg() -> SendGridAPIClient:
    global _sg
    if _sg is None:
        _sg = SendGridAPIClient(settings.sendgrid_api_key)
    return _sg


# ─── SMS ──────────────────────────────────────────────────────────────────────

def send_sms(to: str, body: str) -> str:
    """Send an SMS. Returns Twilio message SID."""
    msg = _get_twilio().messages.create(
        body=body[:1600],  # Twilio limit
        from_=settings.twilio_from_number,
        to=to,
    )
    logger.info("SMS sent to %s — SID: %s", to, msg.sid)
    return msg.sid


# ─── Email ────────────────────────────────────────────────────────────────────

def send_email(
    to_email: str,
    to_name: str,
    subject: str,
    body: str,
    html_body: str | None = None,
    attachment_path: str | None = None,
) -> None:
    """Send an email via SendGrid, optionally with a PDF attachment."""
    message = Mail(
        from_email=(settings.email_from, settings.email_from_name),
        to_emails=[(to_email, to_name)],
        subject=subject,
        plain_text_content=body,
        html_content=html_body or body.replace("\n", "<br>"),
    )

    if attachment_path and Path(attachment_path).exists():
        with open(attachment_path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        att = Attachment()
        att.file_content = FileContent(data)
        att.file_name = FileName(Path(attachment_path).name)
        att.file_type = FileType("application/pdf")
        att.disposition = Disposition("attachment")
        message.attachment = att

    _get_sg().send(message)
    logger.info("Email sent to %s — %s", to_email, subject)


def email_owner(subject: str, body: str, attachment_path: str | None = None) -> None:
    send_email(
        to_email=settings.owner_email,
        to_name="Captain Taxi Owner",
        subject=subject,
        body=body,
        attachment_path=attachment_path,
    )


# ─── Invoice-specific helpers ─────────────────────────────────────────────────

def email_invoice(
    to_email: str,
    to_name: str,
    invoice,       # Invoice model instance
    account,       # CorporateAccount model instance
    pdf_path: str | None = None,
) -> None:
    period = f"{invoice.period_start.strftime('%B %d')} – {invoice.period_end.strftime('%B %d, %Y')}"
    body = f"""Dear {to_name},

Please find attached your invoice from Captain Taxi for the period {period}.

Invoice #:  {invoice.invoice_number}
Period:     {period}
Subtotal:   ${invoice.subtotal:.2f}
GST (5%):   ${invoice.gst_amount:.2f}
TOTAL:      ${invoice.total:.2f}
Due Date:   {invoice.due_date.strftime('%B %d, %Y') if invoice.due_date else 'Net 30'}

Payment options:
• EFT / e-Transfer: accounts@captain.taxi
• Cheque payable to: Captain Taxi Ltd.

For questions, reply to this email or call 306-242-0000 (Saskatoon) / 306-775-2222 (Regina).

Thank you for your business!

Captain Taxi Accounts
"""
    send_email(
        to_email=to_email,
        to_name=to_name,
        subject=f"Invoice {invoice.invoice_number} — Captain Taxi — ${invoice.total:.2f} due {invoice.due_date}",
        body=body,
        attachment_path=pdf_path,
    )


def email_invoice_reminder(
    to_email: str,
    to_name: str,
    invoice,
    days_overdue: int,
    escalated: bool = False,
) -> None:
    urgency = "FINAL NOTICE — " if escalated else ""
    body = f"""Dear {to_name},

{urgency}This is a reminder that invoice {invoice.invoice_number} is {days_overdue} days past due.

Invoice #:  {invoice.invoice_number}
Amount Due: ${invoice.total:.2f}
Due Date:   {invoice.due_date}

{"We kindly ask that you arrange payment immediately to avoid service interruption." if escalated else "Please arrange payment at your earliest convenience."}

To pay: e-Transfer to accounts@captain.taxi or call 306-242-0000.

Captain Taxi Accounts
"""
    subject = (
        f"{'FINAL NOTICE — ' if escalated else ''}Payment Overdue: Invoice {invoice.invoice_number} — ${invoice.total:.2f}"
    )
    send_email(to_email=to_email, to_name=to_name, subject=subject, body=body)
