"""
ElevenLabs Conversational AI webhook.

ElevenLabs invokes this endpoint during a phone call for:
  - client tool calls (book_trip, get_trip_status, cancel_trip, transfer_to_human)
  - post-call reports (final summary, transcript)

The bot streams every event into the LogBroker so the dashboard sees the call
unfold in real time.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Request, Response

from config import get_settings
from services import dispatch_client
from services.difficulty import (
    record_tool_failure,
    reset_tool_failures,
    should_transfer_on_failure,
    transcript_requests_human,
)
from services.log_stream import log_broker
from services.transfer import transfer_call

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/webhook/elevenlabs", tags=["elevenlabs"])


def _verify_signature(request: Request, body: bytes) -> bool:
    if not settings.elevenlabs_webhook_secret:
        return True
    sig = request.headers.get("x-elevenlabs-signature", "")
    expected = hmac.new(
        settings.elevenlabs_webhook_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(sig, expected)


def _call_id(payload: dict) -> str:
    return (
        payload.get("conversation_id")
        or payload.get("call_id")
        or payload.get("call", {}).get("sid")
        or "unknown"
    )


def _twilio_sid(payload: dict) -> str | None:
    return (
        payload.get("twilio_call_sid")
        or payload.get("call", {}).get("twilio_sid")
        or payload.get("call", {}).get("sid")
    )


def _caller_phone(payload: dict) -> str | None:
    return (
        payload.get("caller_phone")
        or payload.get("from")
        or payload.get("call", {}).get("from")
    )


# ── Client tool dispatch table ───────────────────────────────────────────────


async def _tool_book_trip(args: dict, call_id: str, caller_phone: str | None) -> dict:
    res = await dispatch_client.create_trip(
        customer_phone=args.get("customer_phone") or caller_phone or "",
        customer_name=args.get("customer_name"),
        pickup_address=args["pickup_address"],
        dropoff_address=args["dropoff_address"],
        city=args.get("city"),
        notes=args.get("notes"),
    )
    await log_broker.publish(call_id, "trip_booked", {"trip_id": res.get("trip_id"), "city": res.get("city")})
    return res


async def _tool_get_trip_status(args: dict, call_id: str, caller_phone: str | None) -> dict:
    return await dispatch_client.get_trip_status(args["trip_id"])


async def _tool_cancel_trip(args: dict, call_id: str, caller_phone: str | None) -> dict:
    return await dispatch_client.cancel_trip(args["trip_id"], args.get("reason", "Customer request"))


async def _tool_transfer_to_human(args: dict, call_id: str, caller_phone: str | None) -> dict:
    sid = args.get("twilio_call_sid")
    if not sid:
        return {"status": "error", "error": "no twilio_call_sid supplied"}
    city = args.get("city") or "saskatoon"
    res = await transfer_call(sid, city=city, reason=args.get("reason", "bot requested"))
    await log_broker.publish(call_id, "transferred_to_human", res)
    return res


_TOOLS = {
    "book_trip": _tool_book_trip,
    "get_trip_status": _tool_get_trip_status,
    "cancel_trip": _tool_cancel_trip,
    "transfer_to_human": _tool_transfer_to_human,
}


@router.post("/call")
async def elevenlabs_webhook(request: Request):
    body = await request.body()
    if not _verify_signature(request, body):
        return Response(status_code=403, content="Forbidden")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return Response(status_code=400, content="Invalid JSON")

    event_type = payload.get("type") or payload.get("event_type")
    call_id = _call_id(payload)
    caller_phone = _caller_phone(payload)

    # ── Call started ─────────────────────────────────────────────────────────
    if event_type in ("call.started", "conversation.started"):
        await log_broker.publish(call_id, "call_started", {"from": caller_phone})
        return {"status": "ok"}

    # ── User utterance — check for "speak to a human" trigger ────────────────
    if event_type in ("user_message", "transcript.user"):
        text = payload.get("text") or payload.get("message")
        await log_broker.publish(call_id, "user_message", {"text": text})
        if transcript_requests_human(text):
            sid = _twilio_sid(payload)
            if sid:
                res = await transfer_call(sid, city=payload.get("city", "saskatoon"), reason="user requested human")
                await log_broker.publish(call_id, "auto_transfer", res)
        return {"status": "ok"}

    if event_type in ("assistant_message", "transcript.assistant"):
        await log_broker.publish(call_id, "assistant_message", {"text": payload.get("text")})
        return {"status": "ok"}

    # ── Tool call ────────────────────────────────────────────────────────────
    if event_type in ("tool_call", "client_tool_call"):
        tool_name = payload.get("tool_name") or payload.get("name")
        tool_args = payload.get("parameters") or payload.get("arguments") or {}
        if isinstance(tool_args, str):
            try:
                tool_args = json.loads(tool_args)
            except Exception:
                tool_args = {}

        await log_broker.publish(call_id, "tool_call", {"tool": tool_name, "args": tool_args})

        handler = _TOOLS.get(tool_name)
        if not handler:
            await log_broker.publish(call_id, "tool_unknown", {"tool": tool_name})
            return {"result": f"Unknown tool: {tool_name}"}

        try:
            result = await handler(tool_args, call_id, caller_phone)
            reset_tool_failures(call_id)
            await log_broker.publish(call_id, "tool_result", {"tool": tool_name, "result": result})
            return {"result": result}
        except Exception as e:
            logger.exception("Tool %s failed on call %s", tool_name, call_id)
            failures = record_tool_failure(call_id)
            await log_broker.publish(
                call_id,
                "tool_error",
                {"tool": tool_name, "error": str(e), "consecutive_failures": failures},
            )
            if should_transfer_on_failure(call_id):
                sid = _twilio_sid(payload)
                if sid:
                    res = await transfer_call(sid, reason=f"{failures} tool failures")
                    await log_broker.publish(call_id, "auto_transfer", res)
            return {"result": f"That action failed: {e}"}

    # ── Call ended ───────────────────────────────────────────────────────────
    if event_type in ("call.ended", "conversation.ended", "end-of-call-report"):
        reset_tool_failures(call_id)
        await log_broker.publish(
            call_id,
            "call_ended",
            {
                "summary": payload.get("summary"),
                "duration_s": payload.get("duration_seconds") or payload.get("duration"),
            },
        )
        return {"status": "ok"}

    # Unknown event — log and ack so ElevenLabs doesn't retry.
    await log_broker.publish(call_id, "unknown_event", {"event_type": event_type})
    return {"status": "ok"}
