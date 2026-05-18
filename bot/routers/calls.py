"""
Manual call controls for dispatchers.

  GET  /calls/{call_id}/history   — replay all events for a call (mid-call join)
  POST /calls/{call_id}/transfer  — manually warm-transfer to a human
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.log_stream import log_broker
from services.transfer import transfer_call

router = APIRouter(prefix="/calls", tags=["calls"])


class TransferRequest(BaseModel):
    twilio_call_sid: str
    city: str = "saskatoon"
    reason: str = "manual transfer"


@router.get("/{call_id}/history")
async def call_history(call_id: str):
    events = await log_broker.history(call_id)
    if not events:
        raise HTTPException(status_code=404, detail="No history for that call")
    return {"call_id": call_id, "events": events}


@router.post("/{call_id}/transfer")
async def manual_transfer(call_id: str, body: TransferRequest):
    res = await transfer_call(body.twilio_call_sid, city=body.city, reason=body.reason)
    await log_broker.publish(call_id, "manual_transfer", res)
    return res
