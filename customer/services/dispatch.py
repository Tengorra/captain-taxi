"""
Dispatch Agent API client.

Sends a standardised trip object to the Dispatch Agent and returns
the trip ID + any confirmation details.
"""

from __future__ import annotations
import httpx
from datetime import datetime
from config import get_settings

settings = get_settings()

HEADERS = {
    "Content-Type": "application/json",
    "X-Api-Key": settings.dispatch_agent_api_key,
}

_SASKATOON_KEYWORDS = ("saskatoon", "yxe", "warman", "martensville", "osler", "clavet")
_REGINA_KEYWORDS    = ("regina", "yqr", "white city", "emerald park", "pilot butte", "lumsden")


def _infer_city(pickup: str, dropoff: str) -> str:
    """Best-effort city detection from address strings. Defaults to saskatoon."""
    combined = (pickup + " " + dropoff).lower()
    if any(k in combined for k in _REGINA_KEYWORDS):
        return "regina"
    return "saskatoon"


class DispatchError(Exception):
    pass


_VALID_BOOKING_SOURCES = {"phone", "app", "web", "whatsapp", "agent"}


async def create_trip(
    customer_phone: str,
    customer_name: str | None,
    pickup_address: str,
    dropoff_address: str,
    city: str | None = None,
    num_passengers: int = 1,
    notes: str | None = None,
    scheduled_for: datetime | None = None,
    internal_booking_id: str | None = None,
    booking_source: str = "agent",
) -> dict:
    """
    POST /dispatch/trip to the Dispatch Agent.
    Returns the dispatch response dict (at minimum: {"id": "...", "status": "..."}).
    """
    resolved_city = (city or _infer_city(pickup_address, dropoff_address)).lower().strip()
    source = booking_source if booking_source in _VALID_BOOKING_SOURCES else "agent"

    payload = {
        "customer_phone": customer_phone,
        "customer_name": customer_name or "",
        "pickup_address": pickup_address,
        "dropoff_address": dropoff_address,
        "city": resolved_city,
        "notes": notes or "",
        "scheduled_for": scheduled_for.isoformat() if scheduled_for else None,
        "booking_source": source,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(
                f"{settings.dispatch_agent_url}/dispatch/trip",
                json=payload,
                headers=HEADERS,
            )
            resp.raise_for_status()
            data = resp.json()
            # Normalise: callers expect a "trip_id" key
            if "trip_id" not in data and "id" in data:
                data["trip_id"] = data["id"]
            return data
        except httpx.HTTPStatusError as e:
            raise DispatchError(f"Dispatch agent returned {e.response.status_code}: {e.response.text}") from e
        except httpx.RequestError as e:
            raise DispatchError(f"Could not reach dispatch agent: {e}") from e


async def get_trip_status(trip_id: str) -> dict:
    """GET /dispatch/trip/{trip_id} — returns status, ETA, driver info."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                f"{settings.dispatch_agent_url}/dispatch/trip/{trip_id}",
                headers=HEADERS,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise DispatchError(f"Dispatch agent returned {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise DispatchError(f"Could not reach dispatch agent: {e}") from e


async def cancel_trip(trip_id: str, reason: str = "Customer request") -> dict:
    """POST /dispatch/trip/{trip_id}/cancel."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{settings.dispatch_agent_url}/dispatch/trip/{trip_id}/cancel",
                json={"reason": reason},
                headers=HEADERS,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise DispatchError(f"Dispatch agent returned {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise DispatchError(f"Could not reach dispatch agent: {e}") from e
