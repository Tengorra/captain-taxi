"""
ElevenLabs Agents (Conversational AI) inbound webhook surface.

ElevenLabs configures each tool independently in their dashboard as a
discrete REST call — they do NOT funnel all tool calls through one
webhook the way Vapi does. So we expose one small endpoint per tool,
plus a post-call webhook for the end-of-call summary.

Configure each tool in the ElevenLabs dashboard to:
  - Method:        POST (or GET where noted)
  - URL:           https://customer.captain.taxi/voice/<endpoint>
  - Content type:  application/json
  - Body:          map the LLM-extracted parameters into the JSON keys
                   documented on each endpoint below
  - Auth header:   X-Captain-Auth = <ELEVENLABS_WEBHOOK_SECRET>
                   (header name is configurable via the
                    `elevenlabs_auth_header` setting)

System parameters (caller id, conversation id) are passed through
the JSON body — the ElevenLabs dashboard exposes placeholders such as
{{system__caller_id}} and {{system__conversation_id}} that you map
into `caller_phone` and `conversation_id` on the request.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from db.database import get_db
from db.customers import (
    get_or_create_customer,
    save_booking,
    log_complaint as db_log_complaint,
    get_recent_bookings,
)
from db.models import Channel, ComplaintSeverity
from services import dispatch as dispatch_svc
from services.notify import alert_owner_escalation

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/voice", tags=["voice (elevenlabs)"])


# ── Auth ───────────────────────────────────────────────────────────────────


async def verify_voice_auth(request: Request) -> None:
    """
    Validate the shared-secret header on every inbound tool call.
    If no secret is configured, auth is skipped (useful for local dev,
    but you should always set the secret in production).
    """
    if not settings.elevenlabs_webhook_secret:
        return
    header_name = settings.elevenlabs_auth_header
    supplied = request.headers.get(header_name) or request.headers.get(header_name.lower())
    if not supplied:
        raise HTTPException(status_code=401, detail=f"Missing {header_name} header")
    if not hmac.compare_digest(supplied, settings.elevenlabs_webhook_secret):
        raise HTTPException(status_code=403, detail="Bad auth")


def _verify_post_call_signature(body: bytes, signature: str | None) -> bool:
    """
    Optional HMAC-SHA256 verification on the post-call webhook.
    ElevenLabs signs post-call webhook deliveries with a workspace secret.
    """
    if not settings.elevenlabs_webhook_secret:
        return True
    if not signature:
        return False
    expected = hmac.new(
        settings.elevenlabs_webhook_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    # Accept both "sha256=<hex>" and bare hex.
    supplied = signature.replace("sha256=", "")
    return hmac.compare_digest(supplied, expected)


# ── Request bodies ─────────────────────────────────────────────────────────


class BookingRequest(BaseModel):
    pickup_address: str = Field(..., min_length=3)
    dropoff_address: str = Field(..., min_length=3)
    customer_name: Optional[str] = ""
    customer_phone: Optional[str] = ""
    caller_phone: Optional[str] = ""  # filled by ElevenLabs {{system__caller_id}}
    num_passengers: int = 1
    pickup_time: str = "ASAP"
    notes: Optional[str] = ""
    city: Optional[str] = None
    conversation_id: Optional[str] = ""


class TripIdRequest(BaseModel):
    trip_id: str
    caller_phone: Optional[str] = ""
    conversation_id: Optional[str] = ""


class CancelRequest(BaseModel):
    trip_id: str
    reason: str = "Customer request"
    caller_phone: Optional[str] = ""


class FareEstimateRequest(BaseModel):
    pickup_address: str
    dropoff_address: str
    after_hours: bool = False


class ComplaintRequest(BaseModel):
    description: str
    severity: str = "minor"
    trip_id: Optional[str] = None
    caller_phone: Optional[str] = ""


class LookupRequest(BaseModel):
    customer_phone: Optional[str] = ""
    caller_phone: Optional[str] = ""


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.post("/booking", dependencies=[Depends(verify_voice_auth)])
async def create_booking(req: BookingRequest, db: AsyncSession = Depends(get_db)):
    """
    Create a booking. Configure this as the `create_booking` tool in
    ElevenLabs. Returns plain-language confirmation text the agent can
    read back to the caller.
    """
    phone = req.customer_phone or req.caller_phone
    if not phone:
        return {"result": "I need a phone number to confirm the booking — could you read it back to me?"}

    customer = await get_or_create_customer(db, phone=phone, name=req.customer_name or None)

    pickup_dt = None
    if req.pickup_time and req.pickup_time.upper() != "ASAP":
        try:
            pickup_dt = datetime.fromisoformat(req.pickup_time)
        except ValueError:
            pickup_dt = None

    try:
        dispatch_resp = await dispatch_svc.create_trip(
            customer_phone=phone,
            customer_name=req.customer_name or None,
            pickup_address=req.pickup_address,
            dropoff_address=req.dropoff_address,
            city=req.city,
            notes=req.notes or None,
            scheduled_for=pickup_dt,
            booking_source="phone",
        )
        trip_id = dispatch_resp.get("trip_id") or dispatch_resp.get("id")
    except dispatch_svc.DispatchError as e:
        logger.warning("Dispatch failed: %s", e)
        return {"result": "Sorry, I couldn't reach dispatch — please try again in a moment."}

    await save_booking(
        db,
        customer=customer,
        channel=Channel.PHONE,
        pickup=req.pickup_address,
        dropoff=req.dropoff_address,
        trip_id=trip_id,
        pickup_time=pickup_dt,
        num_passengers=req.num_passengers,
        notes=req.notes,
        dispatch_ref=dispatch_resp,
    )

    if pickup_dt is None:
        spoken = (
            f"You're all set. Booking confirmed for pickup at {req.pickup_address}, "
            f"dropoff at {req.dropoff_address}. A driver will be with you shortly."
        )
    else:
        when = pickup_dt.strftime("%B %d at %I:%M %p")
        spoken = (
            f"Booked. Pickup at {req.pickup_address} on {when}, "
            f"dropoff at {req.dropoff_address}."
        )
    return {"result": spoken, "trip_id": trip_id}


@router.post("/trip-status", dependencies=[Depends(verify_voice_auth)])
async def trip_status(req: TripIdRequest):
    """`get_trip_status` tool."""
    try:
        status = await dispatch_svc.get_trip_status(req.trip_id)
    except dispatch_svc.DispatchError:
        return {"result": f"I couldn't find trip {req.trip_id}. Could you read the trip ID back to me?"}

    driver = status.get("driver_name", "a driver")
    eta = status.get("eta_minutes")
    st = status.get("status", "unknown")
    if eta:
        spoken = f"Trip {req.trip_id}: status is {st}. {driver} is about {eta} minutes away."
    else:
        spoken = f"Trip {req.trip_id}: status is {st}. No ETA available yet."
    return {"result": spoken}


@router.post("/cancel", dependencies=[Depends(verify_voice_auth)])
async def cancel_booking(req: CancelRequest):
    """`cancel_trip` tool."""
    try:
        await dispatch_svc.cancel_trip(req.trip_id, reason=req.reason)
        return {"result": f"Trip {req.trip_id} has been cancelled."}
    except dispatch_svc.DispatchError as e:
        return {"result": f"I couldn't cancel that trip — {e}"}


@router.post("/fare-estimate", dependencies=[Depends(verify_voice_auth)])
async def fare_estimate(req: FareEstimateRequest):
    """`get_fare_estimate` tool. Pure heuristic — no external call."""
    pickup = req.pickup_address.lower()
    dropoff = req.dropoff_address.lower()
    if any(k in pickup or k in dropoff for k in ("airport", "yxe", "yqr")):
        est = "approximately twenty-five to thirty-five dollars"
    elif "warman" in dropoff or "martensville" in dropoff:
        est = "approximately forty to fifty-five dollars"
    elif "white city" in dropoff or "emerald park" in dropoff:
        est = "approximately twenty-five to thirty-five dollars"
    else:
        est = "approximately twelve to twenty-five dollars depending on exact distance"
    surcharge = " Plus a three-dollar after-hours surcharge." if req.after_hours else ""
    return {"result": f"Fare estimate: {est}.{surcharge} Minimum fare is ten dollars."}


@router.post("/complaint", dependencies=[Depends(verify_voice_auth)])
async def complaint(req: ComplaintRequest, db: AsyncSession = Depends(get_db)):
    """`log_complaint` tool."""
    phone = req.caller_phone or "unknown"
    customer = await get_or_create_customer(db, phone=phone)
    severity = (
        ComplaintSeverity.SERIOUS
        if req.severity.lower() == "serious"
        else ComplaintSeverity.MINOR
    )
    record = await db_log_complaint(
        db,
        customer=customer,
        channel=Channel.PHONE,
        description=req.description,
        severity=severity,
        trip_id=req.trip_id,
    )
    if severity == ComplaintSeverity.SERIOUS:
        try:
            alert_owner_escalation(
                customer_phone=phone,
                complaint_description=req.description,
                trip_id=req.trip_id,
                channel="phone",
            )
        except Exception as e:
            logger.error("Owner alert failed: %s", e)
        spoken = (
            "I'm very sorry about this. Our manager has been alerted and "
            f"will call you back within one hour. Your reference is "
            f"{str(record.id)[:8].upper()}."
        )
    else:
        spoken = (
            "I've logged your complaint and I'm sorry for the experience. "
            f"Reference {str(record.id)[:8].upper()}. We'll text you a "
            "discount code on your next booking."
        )
    return {"result": spoken}


@router.post("/lookup-bookings", dependencies=[Depends(verify_voice_auth)])
async def lookup_bookings(req: LookupRequest, db: AsyncSession = Depends(get_db)):
    """`lookup_customer_bookings` tool."""
    phone = req.customer_phone or req.caller_phone
    if not phone:
        return {"result": "I'd need a phone number to look up bookings."}
    customer = await get_or_create_customer(db, phone=phone)
    bookings = await get_recent_bookings(db, customer, limit=3)
    if not bookings:
        return {"result": "No recent bookings on that number."}
    lines = [
        f"{b.trip_id[:8]}: {b.pickup_address} to {b.dropoff_address}, status {b.status.value}"
        for b in bookings
    ]
    return {"result": "Recent bookings: " + "; ".join(lines)}


# ── Post-call webhook ─────────────────────────────────────────────────────


@router.post("/post-call")
async def post_call_webhook(
    request: Request,
    elevenlabs_signature: str | None = Header(default=None, alias="ElevenLabs-Signature"),
    db: AsyncSession = Depends(get_db),
):
    """
    End-of-call webhook from ElevenLabs. Receives the transcript +
    summary so we can persist the call record against the customer.
    Configure the URL in your ElevenLabs workspace webhook settings.
    """
    body = await request.body()
    if not _verify_post_call_signature(body, elevenlabs_signature):
        raise HTTPException(status_code=403, detail="Bad signature")

    import json
    try:
        payload = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Field names vary slightly between Conversational AI payload versions;
    # we read the common ones defensively.
    data = payload.get("data", payload)
    caller_phone = (
        data.get("metadata", {}).get("phone_call", {}).get("external_number")
        or data.get("caller_id")
        or data.get("from_number")
    )
    summary = (
        data.get("analysis", {}).get("transcript_summary")
        or data.get("summary")
        or ""
    )
    conversation_id = data.get("conversation_id") or data.get("call_id") or ""

    logger.info(
        "ElevenLabs call ended — caller=%s conv=%s summary=%.120s",
        caller_phone, conversation_id, summary,
    )

    if caller_phone:
        try:
            await get_or_create_customer(db, phone=caller_phone)
        except Exception:
            pass

    return {"status": "ok"}
