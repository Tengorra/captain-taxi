"""
Live call-log WebSocket.

  ws://bot:8007/calls/stream                — all calls
  ws://bot:8007/calls/stream?call_id=abc    — single call

The dashboard subscribes here to render the call as it happens.
"""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.log_stream import log_broker

logger = logging.getLogger(__name__)
router = APIRouter(tags=["logs"])


@router.websocket("/calls/stream")
async def stream_logs(ws: WebSocket):
    await ws.accept()
    call_filter = ws.query_params.get("call_id")
    q = log_broker.subscribe()

    # Replay history if filtering on a single call.
    if call_filter:
        for event in await log_broker.history(call_filter):
            await ws.send_text(json.dumps(event))

    try:
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=30.0)
            except asyncio.TimeoutError:
                await ws.send_text(json.dumps({"event": "ping"}))
                continue
            if call_filter and event.get("call_id") != call_filter:
                continue
            await ws.send_text(json.dumps(event))
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("log stream socket crashed")
    finally:
        log_broker.unsubscribe(q)
