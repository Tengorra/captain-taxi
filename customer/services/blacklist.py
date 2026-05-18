"""
Blacklist helper — queries admin agent's /api/blacklist/check before a
booking is created. Used by the customer agent so blocked phones/customers
cannot place trips.

Fail-open by design: if the admin service is unreachable, the check returns
{"blocked": False} so a transient outage doesn't lock out real customers.
The owner can still investigate via the Blacklist dashboard page.
"""
from __future__ import annotations
import logging
import httpx

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def check(entity_type: str, entity_value: str) -> dict:
    """Return {"blocked": bool, "reason": str?, "expires_at": str?}."""
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
