"""Thin client around the Dispatch service — the BOT only books trips."""
from __future__ import annotations

import httpx
from datetime import datetime

from config import get_settings

settings = get_settings()

_HEADERS = {
    "Content-Type": "application/json",
    "X-Api-Key": settings.dispatch_agent_api_key,
}

_REGINA_KEYWORDS = ("regina", "yqr", "white city", "emerald park", "pilot butte", "lumsden")


class DispatchError(Exception):
    pass


def infer_city(pickup: str, dropoff: str) -> str:
    combined = (pickup + " " + dropoff).lower()
    if any(k in combined for k in _REGINA_KEYWORDS):
        return "regina"
    return "saskatoon"


async def create_trip(
    customer_phone: str,
    customer_name: str | None,
    pickup_address: str,
    dropoff_address: str,
    city: str | None = None,
    notes: str | None = None,
    scheduled_for: datetime | None = None,
) -> dict:
    payload = {
        "customer_phone": customer_phone,
        "customer_name": customer_name or "",
        "pickup_address": pickup_address,
        "dropoff_address": dropoff_address,
        "city": (city or infer_city(pickup_address, dropoff_address)).lower().strip(),
        "notes": notes or "",
        "scheduled_for": scheduled_for.isoformat() if scheduled_for else None,
        "booking_source": "bot",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(
                f"{settings.dispatch_agent_url}/dispatch/trip",
                json=payload,
                headers=_HEADERS,
            )
            resp.raise_for_status()
            data = resp.json()
            if "trip_id" not in data and "id" in data:
                data["trip_id"] = data["id"]
            return data
        except httpx.HTTPStatusError as e:
            raise DispatchError(f"Dispatch returned {e.response.status_code}: {e.response.text}") from e
        except httpx.RequestError as e:
            raise DispatchError(f"Could not reach dispatch: {e}") from e


async def get_trip_status(trip_id: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                f"{settings.dispatch_agent_url}/dispatch/trip/{trip_id}",
                headers=_HEADERS,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise DispatchError(f"Dispatch returned {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise DispatchError(f"Could not reach dispatch: {e}") from e


async def cancel_trip(trip_id: str, reason: str = "Customer request") -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{settings.dispatch_agent_url}/dispatch/trip/{trip_id}/cancel",
                json={"reason": reason},
                headers=_HEADERS,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise DispatchError(f"Dispatch returned {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise DispatchError(f"Could not reach dispatch: {e}") from e
