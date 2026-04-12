"""
Twilio webhook endpoints.

POST /webhook/twilio/sms       — Inbound SMS
POST /webhook/twilio/whatsapp  — Inbound WhatsApp

Both validate Twilio request signatures, look up/create conversation state,
run Claude, persist state, and reply via TwiML.
"""

import logging
from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse

from config import get_settings
from db.database import get_db
from db.customers import get_or_create_customer
from db.models import Channel
from services.redis_state import append_messages, get_conversation
from ai.conversation import run_conversation

logger   = logging.getLogger(__name__)
settings = get_settings()
router   = APIRouter(prefix="/webhook/twilio", tags=["twilio"])

validator = RequestValidator(settings.twilio_auth_token)


def _validate_twilio(request: Request, form: dict) -> bool:
    url       = str(request.url)
    signature = request.headers.get("X-Twilio-Signature", "")
    return validator.validate(url, form, signature)


def _twiml_reply(text: str) -> Response:
    resp = MessagingResponse()
    resp.message(text)
    return Response(content=str(resp), media_type="text/xml")


async def _handle_inbound(
    request: Request,
    channel: Channel,
    db: AsyncSession,
) -> Response:
    form = dict(await request.form())

    if not _validate_twilio(request, form):
        logger.warning("Invalid Twilio signature from %s", request.client.host if request.client else "unknown")
        return Response(status_code=403, content="Forbidden")

    from_number = form.get("From", "")
    body        = (form.get("Body") or "").strip()

    # Normalise WhatsApp prefix
    caller_phone = from_number.replace("whatsapp:", "")

    if not body:
        return _twiml_reply("Hi there! How can I help you today? You can book a taxi, check your trip status, or ask us anything.")

    # Quick shortcut: CANCEL <trip_id>
    if body.upper().startswith("CANCEL "):
        trip_id = body.split(None, 1)[1].strip()
        body = f"Please cancel my booking {trip_id}"

    # Load conversation state
    messages = await get_conversation(channel.value, caller_phone)

    # Ensure customer exists
    try:
        await get_or_create_customer(db, phone=caller_phone)
    except Exception as e:
        logger.warning("Could not upsert customer %s: %s", caller_phone, e)

    # Append user message
    messages = await append_messages(
        channel.value,
        caller_phone,
        [{"role": "user", "content": body}],
    )

    # Run Claude
    try:
        reply, updated_messages = await run_conversation(
            messages=messages,
            db=db,
            channel=channel,
            caller_phone=caller_phone,
        )
    except Exception as e:
        logger.exception("Conversation failed for %s", caller_phone)
        reply = "Sorry, I'm having technical difficulties. Please call us directly: 306-242-0000."
        updated_messages = messages

    # Persist updated conversation
    # updated_messages already has the new assistant turn appended inside run_conversation
    from services.redis_state import set_conversation
    await set_conversation(channel.value, caller_phone, updated_messages)

    # SMS has a 1600-char limit — truncate gracefully
    if len(reply) > 1500:
        reply = reply[:1497] + "..."

    return _twiml_reply(reply)


@router.post("/sms")
async def sms_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    return await _handle_inbound(request, Channel.SMS, db)


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    return await _handle_inbound(request, Channel.WHATSAPP, db)
