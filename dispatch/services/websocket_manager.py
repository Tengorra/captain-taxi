"""
WebSocket connection manager.

Supports two channel types:
  - "dashboard"  : dispatcher dashboards (broadcast all driver/trip updates)
  - "driver:{id}": a specific driver's mobile app
"""

import json
import logging
from typing import Any
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # channel -> list of active WebSocket connections
        self._channels: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, channel: str):
        await websocket.accept()
        self._channels.setdefault(channel, []).append(websocket)
        logger.info("WS connected: channel=%s total=%d", channel, len(self._channels[channel]))

    def disconnect(self, websocket: WebSocket, channel: str):
        conns = self._channels.get(channel, [])
        if websocket in conns:
            conns.remove(websocket)
        logger.info("WS disconnected: channel=%s remaining=%d", channel, len(conns))

    async def broadcast(self, channel: str, payload: dict[str, Any]):
        """Send a JSON message to all connections on a channel."""
        conns = self._channels.get(channel, [])
        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, channel)

    async def broadcast_dashboard(self, event: str, data: dict[str, Any]):
        await self.broadcast("dashboard", {"event": event, "data": data})

    async def notify_driver(self, driver_id: str, event: str, data: dict[str, Any]):
        await self.broadcast(f"driver:{driver_id}", {"event": event, "data": data})


# Singleton shared across the app
ws_manager = ConnectionManager()
