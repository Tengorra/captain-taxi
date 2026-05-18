import os
import base64
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Mail, Attachment, FileContent, FileName, FileType, Disposition
)
from dotenv import load_dotenv

load_dotenv()

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@captain.taxi")
OWNER_EMAIL = os.getenv("OWNER_EMAIL", "")
AMARA_EMAIL = os.getenv("AMARA_EMAIL", "")


def send_email(to: str | list[str], subject: str, html_body: str, pdf_bytes: bytes = None, pdf_filename: str = None) -> bool:
    """Send an email via SendGrid. Optionally attach a PDF."""
    recipients = [to] if isinstance(to, str) else to
    message = Mail(
        from_email=FROM_EMAIL,
        to_emails=recipients,
        subject=subject,
        html_content=html_body,
    )
    if pdf_bytes and pdf_filename:
        encoded = base64.b64encode(pdf_bytes).decode()
        attachment = Attachment(
            FileContent(encoded),
            FileName(pdf_filename),
            FileType("application/pdf"),
            Disposition("attachment"),
        )
        message.attachment = attachment
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        return response.status_code in (200, 202)
    except Exception as e:
        print(f"[SendGrid] Error sending email: {e}")
        return False


def send_weekly_report(pdf_bytes: bytes, week_label: str) -> bool:
    """Send weekly PDF report to owner and Amara."""
    recipients = [e for e in [OWNER_EMAIL, AMARA_EMAIL] if e]
    subject = f"Captain Taxi — Weekly Report {week_label}"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
      <h2 style="color: #1a1a2e;">Captain Taxi Weekly Report</h2>
      <p>Hi,</p>
      <p>Please find attached the weekly operations report for <strong>{week_label}</strong>.</p>
      <p>This report covers revenue, driver performance, trip statistics, and compliance status
         for both Saskatoon and Regina.</p>
      <hr/>
      <p style="color: #666; font-size: 12px;">Captain Taxi Admin System &mdash; Auto-generated</p>
    </div>
    """
    return send_email(recipients, subject, html, pdf_bytes, f"captain-taxi-report-{week_label}.pdf")
