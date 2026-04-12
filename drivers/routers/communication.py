"""Communication endpoints — direct messages and broadcasts."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.driver import Driver, City
from models.communication import Message
from agents.communication_agent import (
    send_direct_sms, send_direct_email, broadcast_sms
)

router = APIRouter(prefix="/drivers", tags=["communication"])


class DirectSMSRequest(BaseModel):
    message: str


class DirectEmailRequest(BaseModel):
    subject: str
    body_html: str


class BroadcastRequest(BaseModel):
    message: str
    city: Optional[City] = None


@router.post("/{driver_id}/sms")
async def send_sms_to_driver(
    driver_id: int,
    payload: DirectSMSRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Driver).where(Driver.id == driver_id))
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(404, "Driver not found")
    msg = await send_direct_sms(driver, payload.message, db)
    return {"message_id": msg.id, "status": msg.status.value}


@router.post("/{driver_id}/email")
async def send_email_to_driver(
    driver_id: int,
    payload: DirectEmailRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Driver).where(Driver.id == driver_id))
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(404, "Driver not found")
    msg = await send_direct_email(driver, payload.subject, payload.body_html, db)
    return {"message_id": msg.id, "status": msg.status.value}


@router.post("/broadcast/sms")
async def broadcast_sms_to_drivers(
    payload: BroadcastRequest,
    db: AsyncSession = Depends(get_db),
):
    broadcast = await broadcast_sms(
        body=payload.message,
        db=db,
        city=payload.city,
        sent_by="admin",
    )
    return {
        "broadcast_id": broadcast.id,
        "recipients": len(broadcast.recipients),
        "city": payload.city.value if payload.city else "all",
    }


@router.get("/{driver_id}/messages")
async def get_driver_messages(
    driver_id: int,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Message)
        .where(Message.driver_id == driver_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    messages = result.scalars().all()
    return [
        {
            "id": m.id,
            "direction": m.direction.value,
            "channel": m.channel.value,
            "body": m.body,
            "status": m.status.value,
            "created_at": m.created_at,
        }
        for m in messages
    ]
