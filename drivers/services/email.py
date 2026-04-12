"""Email service — SendGrid preferred, SMTP fallback."""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)


async def send_email(
    to: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
) -> bool:
    """Send email. Uses SendGrid if API key provided, else SMTP."""
    if settings.sendgrid_api_key:
        return await _send_sendgrid(to, subject, html_body, text_body)
    elif settings.smtp_host:
        return await _send_smtp(to, subject, html_body, text_body)
    else:
        logger.error("No email provider configured (SENDGRID_API_KEY or SMTP_HOST required)")
        return False


async def _send_sendgrid(to: str, subject: str, html_body: str, text_body: Optional[str]) -> bool:
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail, Email, To, Content

        sg = sendgrid.SendGridAPIClient(api_key=settings.sendgrid_api_key)
        message = Mail(
            from_email=Email(settings.from_email, settings.from_name),
            to_emails=To(to),
            subject=subject,
            html_content=Content("text/html", html_body),
        )
        if text_body:
            message.content = [
                Content("text/plain", text_body),
                Content("text/html", html_body),
            ]
        response = sg.send(message)
        success = response.status_code in (200, 201, 202)
        if not success:
            logger.error(f"SendGrid error {response.status_code} sending to {to}")
        return success
    except Exception as e:
        logger.error(f"SendGrid exception sending to {to}: {e}")
        return False


async def _send_smtp(to: str, subject: str, html_body: str, text_body: Optional[str]) -> bool:
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.from_name} <{settings.from_email}>"
        msg["To"] = to

        if text_body:
            msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.ehlo()
            server.starttls()
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.from_email, to, msg.as_string())
        logger.info(f"Email sent via SMTP to {to}")
        return True
    except Exception as e:
        logger.error(f"SMTP error sending to {to}: {e}")
        return False


def onboarding_email_html(driver_name: str, step_label: str, detail: str, portal_url: str) -> str:
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
      <h2 style="color:#1a1a2e">Captain Taxi — Driver Onboarding</h2>
      <p>Hi {driver_name},</p>
      <p>{detail}</p>
      <p style="background:#f4f4f4;padding:12px;border-radius:6px">
        <strong>Next step:</strong> {step_label}
      </p>
      <p>
        <a href="{portal_url}" style="background:#e63946;color:#fff;padding:10px 20px;
           border-radius:4px;text-decoration:none;display:inline-block">
          Complete Your Onboarding
        </a>
      </p>
      <p style="color:#888;font-size:12px">Captain Taxi · Saskatoon & Regina, SK</p>
    </div>
    """


def performance_report_html(driver_name: str, week: str, metrics: dict) -> str:
    cancel_pct = (metrics.get("cancellation_rate") or 0) * 100
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
      <h2 style="color:#1a1a2e">Your Weekly Performance Report</h2>
      <p>Hi {driver_name},</p>
      <p>Here's your performance summary for the week of <strong>{week}</strong>:</p>
      <table style="width:100%;border-collapse:collapse">
        <tr style="background:#f4f4f4">
          <td style="padding:8px;border:1px solid #ddd">Trips Completed</td>
          <td style="padding:8px;border:1px solid #ddd"><strong>{metrics.get('trips_completed', 0)}</strong></td>
        </tr>
        <tr>
          <td style="padding:8px;border:1px solid #ddd">Cancellation Rate</td>
          <td style="padding:8px;border:1px solid #ddd"><strong>{cancel_pct:.1f}%</strong></td>
        </tr>
        <tr style="background:#f4f4f4">
          <td style="padding:8px;border:1px solid #ddd">Average Rating</td>
          <td style="padding:8px;border:1px solid #ddd"><strong>{metrics.get('avg_rating', 'N/A')}</strong></td>
        </tr>
        <tr>
          <td style="padding:8px;border:1px solid #ddd">Income Earned</td>
          <td style="padding:8px;border:1px solid #ddd"><strong>${metrics.get('income_earned', 0):.2f}</strong></td>
        </tr>
        <tr style="background:#f4f4f4">
          <td style="padding:8px;border:1px solid #ddd">Hours Online</td>
          <td style="padding:8px;border:1px solid #ddd"><strong>{metrics.get('hours_online', 0):.1f} hrs</strong></td>
        </tr>
      </table>
      <p style="color:#888;font-size:12px;margin-top:20px">Captain Taxi · Saskatoon & Regina, SK</p>
    </div>
    """
