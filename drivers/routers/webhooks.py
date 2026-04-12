"""
Twilio webhook — receives inbound SMS from drivers.

Twilio must be configured to POST to: POST /webhooks/sms/inbound
"""
import logging
from fastapi import APIRouter, Depends, Form, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from agents.communication_agent import handle_inbound_sms

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)


@router.post("/sms/inbound")
async def inbound_sms(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Twilio sends a POST here when a driver texts Captain Taxi's number.
    We process it and return a TwiML response (empty — we reply via API, not TwiML).
    """
    logger.info(f"Inbound SMS from {From}: {Body[:80]}")

    try:
        await handle_inbound_sms(from_phone=From, body=Body, db=db)
    except Exception as e:
        logger.error(f"Error handling inbound SMS from {From}: {e}")

    # Return empty TwiML — reply is sent asynchronously via Twilio API
    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
        media_type="application/xml",
    )


@router.post("/sms/status")
async def sms_status_callback(
    MessageSid: str = Form(...),
    MessageStatus: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Twilio delivery status callback.
    Updates message delivery status in the database.
    """
    from sqlalchemy import select, update
    from models.communication import Message, MessageStatus as MsgStatus

    status_map = {
        "delivered": MsgStatus.DELIVERED,
        "failed": MsgStatus.FAILED,
        "undelivered": MsgStatus.FAILED,
        "sent": MsgStatus.SENT,
    }
    new_status = status_map.get(MessageStatus.lower())
    if new_status:
        await db.execute(
            update(Message)
            .where(Message.twilio_sid == MessageSid)
            .values(status=new_status)
        )
        await db.commit()

    logger.debug(f"SMS status callback: SID={MessageSid}, status={MessageStatus}")
    return {"ok": True}
