"""
Redis-backed conversation state management.

Each customer's conversation is stored under key:
  conv:{channel}:{phone_or_session_id}

Value is a JSON list of Claude message objects:
  [{"role": "user"|"assistant", "content": "..."}]

TTL is reset on every read/write.
"""

import json
import redis.asyncio as aioredis
from config import get_settings

settings = get_settings()

_redis: aioredis.Redis | None = None


def _key(channel: str, identifier: str) -> str:
    return f"conv:{channel}:{identifier}"


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def get_conversation(channel: str, identifier: str) -> list[dict]:
    r = await get_redis()
    raw = await r.get(_key(channel, identifier))
    if not raw:
        return []
    await r.expire(_key(channel, identifier), settings.conversation_ttl_seconds)
    return json.loads(raw)


async def set_conversation(channel: str, identifier: str, messages: list[dict]) -> None:
    r = await get_redis()
    await r.setex(
        _key(channel, identifier),
        settings.conversation_ttl_seconds,
        json.dumps(messages),
    )


async def clear_conversation(channel: str, identifier: str) -> None:
    r = await get_redis()
    await r.delete(_key(channel, identifier))


async def append_messages(channel: str, identifier: str, new_messages: list[dict]) -> list[dict]:
    """Load existing messages, append new ones, save and return the full list."""
    messages = await get_conversation(channel, identifier)
    messages.extend(new_messages)
    # Keep last 40 turns to avoid context explosion
    if len(messages) > 40:
        messages = messages[-40:]
    await set_conversation(channel, identifier, messages)
    return messages


# ── Web chat sessions (keyed by session UUID) ─────────────────────────────────

async def get_web_session(session_id: str) -> dict:
    """Return full session state dict for web chat."""
    r = await get_redis()
    raw = await r.get(f"websession:{session_id}")
    if not raw:
        return {"messages": [], "customer_phone": None}
    await r.expire(f"websession:{session_id}", settings.conversation_ttl_seconds)
    return json.loads(raw)


async def set_web_session(session_id: str, state: dict) -> None:
    r = await get_redis()
    await r.setex(
        f"websession:{session_id}",
        settings.conversation_ttl_seconds,
        json.dumps(state),
    )
