"""
Blacklist helper for dispatch — gates new bookings against the admin
agent's /api/blacklist/check endpoint. Fail-open if admin is unreachable
so transient outages don't block real bookings.
"""
from __future__ import annotations
import logging
import httpx

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def check(entity_type: str, entity_value: str) -> dict:
    if not entity_value:
        return {"blocked": False}
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                f"{settings.admin_agent_url}/api/blacklist/check",
                params={"entity_type": entity_type, "entity_value": entity_value},
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.warning("Blacklist check failed (fail-open): %s", e)
        return {"blocked": False}


async def check_phone(phone: str) -> dict:
    return await check("phone", phone)
