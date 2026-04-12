"""
Website chat endpoints.

GET  /chat/widget.js          — Embeddable JS snippet for the Captain Taxi website
POST /chat/message             — Polling-based message endpoint (simpler for most sites)
WS   /chat/ws/{session_id}    — WebSocket endpoint for live chat

Each web chat session is identified by a UUID generated client-side and stored
in localStorage. Conversation state lives in Redis.
"""

import uuid
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Request
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
import pathlib

from config import get_settings
from db.database import get_db
from db.models import Channel
from services.redis_state import (
    get_web_session, set_web_session
)
from ai.conversation import run_conversation

logger   = logging.getLogger(__name__)
settings = get_settings()
router   = APIRouter(prefix="/chat", tags=["chat"])

WIDGET_PATH = pathlib.Path(__file__).parent.parent / "chat" / "widget.js"


@router.get("/widget.js")
async def serve_widget():
    """Serve the embeddable JS snippet."""
    return FileResponse(WIDGET_PATH, media_type="application/javascript")


# ── Polling endpoint (POST) ───────────────────────────────────────────────────

@router.post("/message")
async def chat_message(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Simple polling-based chat for sites that can't use WebSockets.

    Body: { "session_id": "...", "message": "...", "customer_phone": "..." }
    Returns: { "reply": "...", "session_id": "..." }
    """
    body = await request.json()

    session_id     = body.get("session_id") or str(uuid.uuid4())
    user_message   = (body.get("message") or "").strip()
    customer_phone = body.get("customer_phone")

    if not user_message:
        return JSONResponse({"reply": "Hi! How can I help you today?", "session_id": session_id})

    state = await get_web_session(session_id)
    messages = state.get("messages", [])
    if customer_phone:
        state["customer_phone"] = customer_phone

    messages.append({"role": "user", "content": user_message})

    try:
        reply, updated_messages = await run_conversation(
            messages=messages,
            db=db,
            channel=Channel.WEB_CHAT,
            caller_phone=state.get("customer_phone"),
        )
    except Exception as e:
        logger.exception("Web chat conversation failed for session %s", session_id)
        reply = "Sorry, I'm having a technical issue. Please call us at 306-242-0000."
        updated_messages = messages

    state["messages"] = updated_messages
    await set_web_session(session_id, state)

    return JSONResponse({"reply": reply, "session_id": session_id})


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@router.websocket("/ws/{session_id}")
async def chat_websocket(
    websocket: WebSocket,
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    await websocket.accept()
    logger.info("WebSocket connected: session %s", session_id)

    state    = await get_web_session(session_id)
    messages = state.get("messages", [])

    # Send welcome if this is a fresh session
    if not messages:
        await websocket.send_json({
            "type": "message",
            "role": "assistant",
            "content": (
                "Hi there! Welcome to Captain Taxi. "
                "I can book a ride, give you an ETA, cancel a booking, or answer any questions. "
                "How can I help?"
            ),
        })

    try:
        while True:
            data = await websocket.receive_json()
            user_text      = (data.get("content") or "").strip()
            customer_phone = data.get("customer_phone") or state.get("customer_phone")

            if customer_phone:
                state["customer_phone"] = customer_phone

            if not user_text:
                continue

            messages.append({"role": "user", "content": user_text})

            # Send typing indicator
            await websocket.send_json({"type": "typing"})

            try:
                reply, updated_messages = await run_conversation(
                    messages=messages,
                    db=db,
                    channel=Channel.WEB_CHAT,
                    caller_phone=state.get("customer_phone"),
                )
            except Exception as e:
                logger.exception("WS conversation error session %s", session_id)
                reply = "Sorry, I hit a technical issue. Please call 306-242-0000."
                updated_messages = messages

            messages = updated_messages
            state["messages"] = messages
            await set_web_session(session_id, state)

            await websocket.send_json({
                "type": "message",
                "role": "assistant",
                "content": reply,
            })

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: session %s", session_id)
        state["messages"] = messages
        await set_web_session(session_id, state)
