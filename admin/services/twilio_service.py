import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

_client = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = Client(
            os.getenv("TWILIO_ACCOUNT_SID"),
            os.getenv("TWILIO_AUTH_TOKEN"),
        )
    return _client


WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
OWNER_WHATSAPP = os.getenv("OWNER_WHATSAPP", "")
AMARA_WHATSAPP = os.getenv("AMARA_WHATSAPP", "")


def send_whatsapp(to: str, message: str) -> str:
    """Send a WhatsApp message. Returns the message SID."""
    client = get_client()
    msg = client.messages.create(
        from_=WHATSAPP_FROM,
        to=to,
        body=message,
    )
    return msg.sid


def send_owner_alert(message: str) -> list[str]:
    """Send WhatsApp alert to owner (and optionally Amara)."""
    sids = []
    if OWNER_WHATSAPP:
        sids.append(send_whatsapp(OWNER_WHATSAPP, message))
    return sids


def send_sms(to: str, message: str) -> str:
    """Send a plain SMS to a driver."""
    client = get_client()
    from_number = os.getenv("TWILIO_SMS_FROM", os.getenv("TWILIO_WHATSAPP_FROM", "").replace("whatsapp:", ""))
    msg = client.messages.create(
        from_=from_number,
        to=to,
        body=message,
    )
    return msg.sid


def broadcast_sms(phone_numbers: list[str], message: str) -> dict:
    """Send SMS to a list of phone numbers. Returns {phone: sid} map."""
    results = {}
    for phone in phone_numbers:
        try:
            sid = send_sms(phone, message)
            results[phone] = {"status": "sent", "sid": sid}
        except Exception as e:
            results[phone] = {"status": "failed", "error": str(e)}
    return results
