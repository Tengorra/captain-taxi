"""
ElevenLabs Conversational AI webhook endpoints.

The voice agent (configured in the ElevenLabs dashboard) handles STT, LLM,
turn-taking, and TTS. It calls back here for two reasons:

  1. POST /webhook/elevenlabs/tool       — server-tool execution during a call.
     Each tool the agent runs (create_booking, get_trip_status, etc.) is
     configured as a "Server Tool" pointing at this URL. The tool name is in
     the payload and we delegate to the same _execute_tool used by SMS/WhatsApp.

  2. POST /webhook/elevenlabs/post-call  — post-call summary + transcript.
     Logged for review and the caller is upserted as a customer.

Phone routing: an ElevenLabs agent is bound to a Twilio number via the
"Phone numbers" tab on the agent. No TwiML is needed on our side for the
default integration.
"""

import hmac
import hashlib
import json
import logging
import time
from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from db.database import get_db
from db.customers import get_or_create_customer
from db.models import Channel
from ai.conversation import _execute_tool

logger   = logging.getLogger(__name__)
settings = get_settings()
router   = APIRouter(prefix="/webhook/elevenlabs", tags=["elevenlabs"])

SIGNATURE_TOLERANCE_SECONDS = 30 * 60  # 30 min window for replay protection


def _verify_signature(request: Request, body: bytes) -> bool:
    """
    ElevenLabs sends header `ElevenLabs-Signature: t=<unix>,v0=<hmac>`.
    HMAC is sha256 over `<t>.<raw_body>` using the agent's webhook secret.
    Returns True when verification is skipped (no secret configured) — useful
    in dev, but ELEVENLABS_WEBHOOK_SECRET should always be set in production.
    """
    secret = settings.elevenlabs_webhook_secret
    if not secret:
        return True

    header = request.headers.get("elevenlabs-signature", "")
    if not header:
        return False

    parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
    ts  = parts.get("t")
    sig = parts.get("v0")
    if not ts or not sig:
        return False

    try:
        ts_int = int(ts)
    except ValueError:
        return False
    if abs(time.time() - ts_int) > SIGNATURE_TOLERANCE_SECONDS:
        return False

    expected = hmac.new(
        secret.encode(),
        f"{ts}.".encode() + body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(sig, expected)


def _extract_caller_phone(payload: dict) -> str | None:
    """Find the caller's phone in the various places ElevenLabs may place it."""
    return (
        payload.get("caller_phone")
        or payload.get("from")
        or payload.get("call", {}).get("from")
        or payload.get("metadata", {}).get("caller_phone")
        or payload.get("metadata", {}).get("from")
        or payload.get("conversation", {}).get("metadata", {}).get("caller_phone")
    )


async def _handle_tool_call(
    request: Request,
    db: AsyncSession,
    tool_name_from_path: str | None,
) -> Response | dict:
    body = await request.body()
    if not _verify_signature(request, body):
        return Response(status_code=403, content="Forbidden")

    try:
        payload = json.loads(body) if body else {}
    except json.JSONDecodeError:
        return Response(status_code=400, content="Invalid JSON")

    # Tool name: path wins (canonical ElevenLabs server-tool shape), then body
    tool_name = tool_name_from_path or payload.get("tool_name") or payload.get("name")
    if not tool_name:
        return Response(status_code=400, content="Missing tool name")

    # Parameters: if payload looks wrapped use "parameters", else treat whole body as args
    if isinstance(payload, dict) and ("parameters" in payload or "arguments" in payload):
        tool_input = payload.get("parameters") or payload.get("arguments") or {}
        if isinstance(tool_input, str):
            try:
                tool_input = json.loads(tool_input)
            except json.JSONDecodeError:
                tool_input = {}
    else:
        # Path-routed: ElevenLabs sends parameters directly as the body
        tool_input = payload if isinstance(payload, dict) else {}

    caller_phone = (
        _extract_caller_phone(payload)
        or request.headers.get("x-elevenlabs-caller-phone")
        or request.headers.get("x-twilio-caller-from")
    )

    try:
        result = await _execute_tool(
            tool_name=tool_name,
            tool_input=tool_input,
            db=db,
            channel=Channel.PHONE,
            caller_phone=caller_phone,
        )
    except Exception as e:
        logger.exception("ElevenLabs tool %s failed", tool_name)
        result = f"Sorry, that action failed: {e}"

    return {"result": result}


@router.post("/tool")
async def tool_webhook_generic(request: Request, db: AsyncSession = Depends(get_db)):
    """Body-routed shape: { "tool_name": "...", "parameters": {...} }."""
    return await _handle_tool_call(request, db, tool_name_from_path=None)


@router.post("/tool/{tool_name}")
async def tool_webhook_path(tool_name: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Path-routed shape (canonical ElevenLabs server tool): parameters are the raw body."""
    return await _handle_tool_call(request, db, tool_name_from_path=tool_name)


@router.post("/post-call")
async def post_call_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Called after a call ends with summary + transcript. Upserts the customer
    record and logs the call for later review.
    """
    body = await request.body()
    if not _verify_signature(request, body):
        return Response(status_code=403, content="Forbidden")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return Response(status_code=400, content="Invalid JSON")

    caller_phone = _extract_caller_phone(payload)
    summary      = payload.get("summary") or payload.get("analysis", {}).get("summary", "")
    duration     = payload.get("duration_seconds") or payload.get("metadata", {}).get("duration_seconds")

    logger.info(
        "Call ended — caller: %s, duration: %ss, summary: %.140s",
        caller_phone, duration, summary,
    )

    if caller_phone:
        try:
            await get_or_create_customer(db, phone=caller_phone)
        except Exception as e:
            logger.warning("Could not upsert customer %s after call: %s", caller_phone, e)

    return {"status": "ok"}
