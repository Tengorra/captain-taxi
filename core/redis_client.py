"""
Redis client — shared message bus for all Captain Taxi agents.

Channels (pub/sub):
  captain.events          — all agents publish here; orchestrator subscribes
  captain.dispatch        — orchestrator publishes tasks for dispatch agent
  captain.customer        — orchestrator publishes tasks for customer agent
  captain.drivers         — orchestrator publishes tasks for drivers agent
  captain.accounts        — orchestrator publishes tasks for accounts agent
  captain.compliance      — orchestrator publishes tasks for compliance agent
  captain.admin           — orchestrator publishes tasks for admin agent
  captain.escalations     — escalation alerts (all agents can subscribe)
"""
import json
import asyncio
from typing import Any, Callable, Awaitable

import redis.asyncio as aioredis

from core.config import get_settings

settings = get_settings()

_pool: aioredis.ConnectionPool | None = None


def get_pool() -> aioredis.ConnectionPool:
    global _pool
    if _pool is None:
        _pool = aioredis.ConnectionPool.from_url(
            settings.redis_url,
            max_connections=20,
            decode_responses=True,
        )
    return _pool


def get_redis() -> aioredis.Redis:
    return aioredis.Redis(connection_pool=get_pool())


# ── Pub/Sub helpers ────────────────────────────────────────────────────────────

CHANNELS = {
    "events": "captain.events",
    "dispatch": "captain.dispatch",
    "customer": "captain.customer",
    "drivers": "captain.drivers",
    "accounts": "captain.accounts",
    "compliance": "captain.compliance",
    "admin": "captain.admin",
    "escalations": "captain.escalations",
}


async def publish(channel_key: str, payload: dict[str, Any]) -> None:
    """Publish a JSON payload to a captain.* channel."""
    r = get_redis()
    channel = CHANNELS.get(channel_key, channel_key)
    await r.publish(channel, json.dumps(payload))
    await r.aclose()


async def subscribe_forever(
    channel_key: str,
    handler: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    """Subscribe to a channel and call handler for every message. Runs forever."""
    r = get_redis()
    channel = CHANNELS.get(channel_key, channel_key)
    pubsub = r.pubsub()
    await pubsub.subscribe(channel)

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    await handler(data)
                except Exception as exc:
                    # Never let a bad message kill the subscriber
                    import structlog
                    log = structlog.get_logger()
                    log.error("redis_handler_error", error=str(exc), raw=message["data"])
    finally:
        await pubsub.unsubscribe(channel)
        await r.aclose()
