"""
Vapi.ai webhook endpoint.

Vapi calls this URL during a phone call to:
  1. Handle tool calls (create_booking, get_trip_status, etc.)
  2. Receive end-of-call reports

Vapi manages the voice + turn-taking; we only handle business logic.

POST /webhook/vapi/call
"""

import hmac
import hashlib
import logging
from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from db.database import get_db
from db.customers import get_or_create_customer
from db.models import Channel
from ai.conversation import _execute_tool

logger   = logging.getLogger(__name__)
settings = get_settings()
router   = APIRouter(prefix="/webhook/vapi", tags=["vapi"])


def _verify_vapi_signature(request: Request, body: bytes) -> bool:
    """Optional HMAC verification if vapi_webhook_secret is set."""
    if not settings.vapi_webhook_secret:
        return True
    sig = request.headers.get("x-vapi-signature", "")
    expected = hmac.new(
        settings.vapi_webhook_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(sig, expected)


@router.post("/call")
async def vapi_call_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Vapi sends events here during a phone call.

    Event types we handle:
    - tool-calls:          Claude (running inside Vapi) wants to execute a tool
    - end-of-call-report:  Summary after the call ends

    Vapi expects a JSON response with "results" for tool-call events.
    """
    body = await request.body()

    if not _verify_vapi_signature(request, body):
        return Response(status_code=403, content="Forbidden")

    import json
    try:
        payload = json.loads(body)
    except Exception:
        return Response(status_code=400, content="Invalid JSON")

    message_type = payload.get("message", {}).get("type") or payload.get("type")

    # ── Tool call event ───────────────────────────────────────────────────────
    if message_type == "tool-calls":
        tool_calls = payload.get("message", {}).get("toolCalls") or payload.get("toolCalls", [])
        caller_phone = (
            payload.get("message", {}).get("call", {}).get("customer", {}).get("number")
            or payload.get("call", {}).get("customer", {}).get("number")
        )

        results = []
        for tc in tool_calls:
            fn_name  = tc.get("function", {}).get("name") or tc.get("name")
            fn_input = tc.get("function", {}).get("arguments") or tc.get("arguments") or {}
            tc_id    = tc.get("id", fn_name)

            if isinstance(fn_input, str):
                try:
                    fn_input = json.loads(fn_input)
                except Exception:
                    fn_input = {}

            try:
                result = await _execute_tool(
                    tool_name=fn_name,
                    tool_input=fn_input,
                    db=db,
                    channel=Channel.PHONE,
                    caller_phone=caller_phone,
                )
            except Exception as e:
                logger.exception("Vapi tool %s failed", fn_name)
                result = f"Sorry, that action failed: {e}"

            results.append({"toolCallId": tc_id, "result": result})

        return {"results": results}

    # ── End-of-call report ────────────────────────────────────────────────────
    elif message_type == "end-of-call-report":
        call = payload.get("message", {}).get("call") or payload.get("call", {})
        caller_phone = call.get("customer", {}).get("number")
        summary      = payload.get("message", {}).get("summary") or payload.get("summary", "")
        duration     = call.get("endedAt") and call.get("startedAt")

        logger.info(
            "Call ended — caller: %s, duration: %s, summary: %.100s",
            caller_phone, duration, summary
        )

        # Upsert customer so they appear in the database even with no booking
        if caller_phone:
            try:
                await get_or_create_customer(db, phone=caller_phone)
            except Exception:
                pass

        return {"status": "ok"}

    # ── Status updates (assistant-request, etc.) — acknowledge ───────────────
    return {"status": "ok"}
