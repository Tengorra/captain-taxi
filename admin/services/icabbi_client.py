"""
Thin iCabbi REST client.

Off by default — `ICABBI_BASE_URL` and `ICABBI_API_KEY` must be set in the
environment for any call to succeed. `IcabbiClient.is_configured()` lets
the sync runner skip cleanly when creds aren't present yet.

Endpoints below mirror what iCabbi exports look like in the operator
console; exact paths may need tweaking once we have live API docs.
Keep the surface narrow — one method per entity we plan to mirror.
"""
from __future__ import annotations
import logging
import os
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class IcabbiNotConfigured(Exception):
    pass


class IcabbiClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.base_url = (base_url or os.getenv("ICABBI_BASE_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("ICABBI_API_KEY", "")
        self.timeout = timeout

    @classmethod
    def is_configured(cls) -> bool:
        return bool(os.getenv("ICABBI_BASE_URL") and os.getenv("ICABBI_API_KEY"))

    def _headers(self) -> dict:
        if not (self.base_url and self.api_key):
            raise IcabbiNotConfigured(
                "ICABBI_BASE_URL and/or ICABBI_API_KEY missing from environment"
            )
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _get(self, path: str, params: Optional[dict] = None) -> Any:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, headers=self._headers(), params=params)
            resp.raise_for_status()
            return resp.json()

    # ── List endpoints (one per entity we mirror) ──────────────────────────
    # All return a list of dicts. Pagination params are best-effort: iCabbi's
    # console paginates differently per entity; tune once live.

    async def list_addresses(self, page: int = 1, per_page: int = 200) -> list[dict]:
        data = await self._get("/api/v1/addresses",
                                params={"page": page, "per_page": per_page})
        return data.get("data", data if isinstance(data, list) else [])

    async def list_areas(self, page: int = 1, per_page: int = 200) -> list[dict]:
        data = await self._get("/api/v1/areas",
                                params={"page": page, "per_page": per_page})
        return data.get("data", data if isinstance(data, list) else [])

    async def list_items(self, page: int = 1, per_page: int = 200) -> list[dict]:
        data = await self._get("/api/v1/items",
                                params={"page": page, "per_page": per_page})
        return data.get("data", data if isinstance(data, list) else [])

    async def list_partners(self, page: int = 1, per_page: int = 200) -> list[dict]:
        data = await self._get("/api/v1/partners",
                                params={"page": page, "per_page": per_page})
        return data.get("data", data if isinstance(data, list) else [])

    async def list_customers(self, page: int = 1, per_page: int = 200) -> list[dict]:
        data = await self._get("/api/v1/customers",
                                params={"page": page, "per_page": per_page})
        return data.get("data", data if isinstance(data, list) else [])

    async def list_drivers(self, page: int = 1, per_page: int = 200) -> list[dict]:
        data = await self._get("/api/v1/drivers",
                                params={"page": page, "per_page": per_page})
        return data.get("data", data if isinstance(data, list) else [])

    async def list_vehicles(self, page: int = 1, per_page: int = 200) -> list[dict]:
        data = await self._get("/api/v1/vehicles",
                                params={"page": page, "per_page": per_page})
        return data.get("data", data if isinstance(data, list) else [])
