"""
Live call-log fanout.

Each event from an in-flight call (utterance, tool-call, transfer, end) is
published to Redis so multiple BOT workers + the dashboard all see the same
stream. WebSocket clients on `/calls/stream` subscribe to this broker.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import redis.asyncio as redis_async

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class LogBroker:
    """In-process pub/sub fed by Redis so logs survive across workers."""

    def __init__(self) -> None:
        self._redis: redis_async.Redis | None = None
        self._pubsub_task: asyncio.Task | None = None
        self._subscribers: set[asyncio.Queue] = set()

    async def start(self) -> None:
        if self._redis is not None:
            return
        self._redis = redis_async.from_url(settings.redis_url, decode_responses=True)
        self._pubsub_task = asyncio.create_task(self._listen())
        logger.info("LogBroker subscribed to Redis channel %s", settings.log_channel)

    async def stop(self) -> None:
        if self._pubsub_task:
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except asyncio.CancelledError:
                pass
        if self._redis:
            await self._redis.aclose()
            self._redis = None

    async def publish(self, call_id: str, event: str, data: dict[str, Any] | None = None) -> None:
        """Push a single log line for a call into the broker."""
        payload = {
            "call_id": call_id,
            "event": event,
            "ts": time.time(),
            "data": data or {},
        }
        msg = json.dumps(payload)
        if self._redis:
            await self._redis.publish(settings.log_channel, msg)
            # Keep last N events per call for replay when a dashboard connects mid-call.
            history_key = f"bot:call_history:{call_id}"
            await self._redis.rpush(history_key, msg)
            await self._redis.expire(history_key, settings.log_ttl_seconds)
        else:
            # Redis not started yet (tests): fan out locally only.
            await self._fanout(payload)

    async def history(self, call_id: str) -> list[dict[str, Any]]:
        if not self._redis:
            return []
        raw = await self._redis.lrange(f"bot:call_history:{call_id}", 0, -1)
        return [json.loads(r) for r in raw]

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    async def _listen(self) -> None:
        assert self._redis is not None
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(settings.log_channel)
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                try:
                    payload = json.loads(message["data"])
                except Exception:
                    continue
                await self._fanout(payload)
        except asyncio.CancelledError:
            await pubsub.unsubscribe(settings.log_channel)
            raise
        except Exception:
            logger.exception("LogBroker listener crashed")

    async def _fanout(self, payload: dict[str, Any]) -> None:
        dead: list[asyncio.Queue] = []
        for q in self._subscribers:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._subscribers.discard(q)


log_broker = LogBroker()
