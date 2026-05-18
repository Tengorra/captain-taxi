"""
iCabbi -> Captain Taxi sync runner.

Each entity has a small `_sync_X` function that:
  1. pulls rows from iCabbi
  2. matches each row to an existing local row by `icabbi_ref`
  3. updates if present, inserts if not
  4. stamps `last_synced_at`

All sync functions return a dict summary: {"created": N, "updated": N, "errors": [...]}.
The top-level `sync_all()` runs every entity sync sequentially and returns a
combined summary. If iCabbi is not configured, every function returns a
summary noting it was skipped — never raises.
"""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

from sqlalchemy.orm import Session

from ..db.database import SessionLocal
from ..db.models import (
    Address, Area, Item, Partner, Driver, Vehicle,
)
from .icabbi_client import IcabbiClient, IcabbiNotConfigured

logger = logging.getLogger(__name__)


def _skipped(entity: str) -> dict:
    return {"entity": entity, "skipped": True, "reason": "iCabbi not configured",
            "created": 0, "updated": 0, "errors": []}


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─── Field mappers ───────────────────────────────────────────────────────────
# These translate raw iCabbi dicts into kwargs for our SQLAlchemy models.
# Keep them defensive: iCabbi sometimes omits fields or returns them under
# slightly different keys depending on which version of the API serves them.

def _map_address(row: dict) -> dict:
    return {
        "label":   row.get("label") or row.get("name"),
        "line1":   row.get("address1") or row.get("line1") or row.get("address") or "",
        "line2":   row.get("address2") or row.get("line2"),
        "city":    row.get("city"),
        "postal":  row.get("postcode") or row.get("postal"),
        "lat":     row.get("lat") or row.get("latitude"),
        "lng":     row.get("lng") or row.get("longitude"),
        "address_type": row.get("type") or "other",
    }


def _map_area(row: dict) -> dict:
    return {
        "name":        row.get("name") or "Unnamed Area",
        "area_type":   "polygon" if row.get("polygon") else "circle",
        "city":        row.get("city"),
        "center_lat":  row.get("center_lat") or row.get("lat"),
        "center_lng":  row.get("center_lng") or row.get("lng"),
        "radius_m":    row.get("radius_m") or row.get("radius"),
        "polygon_geojson": row.get("polygon"),
        "tags":        row.get("tags") or [],
        "active":      row.get("active", True),
    }


def _map_item(row: dict) -> dict:
    code = row.get("code") or row.get("sku") or str(row.get("id"))
    return {
        "code":        code,
        "name":        row.get("name") or code,
        "description": row.get("description"),
        "price":       float(row.get("price") or 0),
        "taxable":     bool(row.get("taxable", True)),
        "active":      bool(row.get("active", True)),
    }


def _map_partner(row: dict) -> dict:
    return {
        "name":            row.get("name") or "Unnamed Partner",
        "contact_name":    row.get("contact_name"),
        "contact_phone":   row.get("phone") or row.get("contact_phone"),
        "contact_email":   row.get("email") or row.get("contact_email"),
        "city":            row.get("city"),
        "commission_rate": float(row.get("commission_rate") or 0.10),
        "active":          bool(row.get("active", True)),
    }


def _map_driver_patch(row: dict) -> dict:
    """Lightweight patch for already-existing Driver rows from iCabbi imports.
    Full schema mapping lives in admin/api/routes/drivers.py for manual imports.
    """
    return {
        "first_name":     row.get("first_name") or row.get("firstName"),
        "last_name":      row.get("last_name") or row.get("lastName"),
        "phone":          row.get("phone"),
        "email":          row.get("email"),
        "vehicle_ref":    row.get("vehicle_ref") or row.get("vehicleRef"),
        "is_active_flag": bool(row.get("active", True)),
    }


def _map_vehicle(row: dict) -> dict:
    return {
        "plate":  row.get("plate") or row.get("registration") or "",
        "make":   row.get("make") or "",
        "model":  row.get("model") or "",
        "year":   int(row.get("year") or 0),
        "color":  row.get("color"),
        "city":   (row.get("city") or "saskatoon").lower(),
    }


# ─── Generic upsert ──────────────────────────────────────────────────────────

def _upsert(db: Session, model, rows: list[dict], mapper, ref_key: str = "id") -> dict:
    """Match by icabbi_ref, update if found, insert if not. Stamps last_synced_at."""
    created = 0
    updated = 0
    errors: list[str] = []
    now = _now()

    for raw in rows:
        try:
            ref = str(raw.get(ref_key) or raw.get("ref") or raw.get("icabbi_ref") or "").strip()
            if not ref:
                errors.append(f"row missing {ref_key}: {raw!r}")
                continue
            existing = db.query(model).filter(model.icabbi_ref == ref).first()
            payload = mapper(raw)
            if existing:
                for k, v in payload.items():
                    if v is not None:
                        setattr(existing, k, v)
                existing.last_synced_at = now
                updated += 1
            else:
                new = model(**{k: v for k, v in payload.items() if v is not None})
                new.icabbi_ref = ref
                new.last_synced_at = now
                db.add(new)
                created += 1
        except Exception as e:
            errors.append(f"{ref_key}={raw.get(ref_key)!r}: {e}")

    db.commit()
    return {"entity": model.__tablename__, "created": created, "updated": updated, "errors": errors}


# ─── Per-entity sync wrappers ────────────────────────────────────────────────

async def sync_addresses(client: IcabbiClient) -> dict:
    rows = await client.list_addresses()
    db = SessionLocal()
    try:
        return _upsert(db, Address, rows, _map_address)
    finally:
        db.close()


async def sync_areas(client: IcabbiClient) -> dict:
    rows = await client.list_areas()
    db = SessionLocal()
    try:
        return _upsert(db, Area, rows, _map_area)
    finally:
        db.close()


async def sync_items(client: IcabbiClient) -> dict:
    rows = await client.list_items()
    db = SessionLocal()
    try:
        return _upsert(db, Item, rows, _map_item)
    finally:
        db.close()


async def sync_partners(client: IcabbiClient) -> dict:
    rows = await client.list_partners()
    db = SessionLocal()
    try:
        return _upsert(db, Partner, rows, _map_partner)
    finally:
        db.close()


async def sync_drivers(client: IcabbiClient) -> dict:
    rows = await client.list_drivers()
    db = SessionLocal()
    try:
        # Drivers are keyed by `ref` in iCabbi exports (matches existing column).
        return _upsert(db, Driver, rows, _map_driver_patch, ref_key="ref")
    finally:
        db.close()


async def sync_vehicles(client: IcabbiClient) -> dict:
    rows = await client.list_vehicles()
    db = SessionLocal()
    try:
        return _upsert(db, Vehicle, rows, _map_vehicle)
    finally:
        db.close()


# ─── Top-level runner ────────────────────────────────────────────────────────

ENTITY_SYNCS: dict[str, Callable[[IcabbiClient], Awaitable[dict]]] = {
    "addresses": sync_addresses,
    "areas":     sync_areas,
    "items":     sync_items,
    "partners":  sync_partners,
    "drivers":   sync_drivers,
    "vehicles":  sync_vehicles,
}


async def sync_all(entities: list[str] | None = None) -> dict:
    """Run sync for the given entity names (or all if None).
    Returns a dict per entity. If iCabbi isn't configured, every entity is
    marked skipped so the caller gets a clean response rather than an error."""
    target = entities or list(ENTITY_SYNCS.keys())

    if not IcabbiClient.is_configured():
        return {"ok": True, "configured": False,
                "results": {e: _skipped(e) for e in target}}

    client = IcabbiClient()
    results: dict[str, Any] = {}
    for name in target:
        fn = ENTITY_SYNCS.get(name)
        if not fn:
            results[name] = {"entity": name, "error": "unknown entity"}
            continue
        try:
            results[name] = await fn(client)
        except IcabbiNotConfigured as e:
            results[name] = _skipped(name) | {"reason": str(e)}
        except Exception as e:
            logger.exception("iCabbi sync failed for %s", name)
            results[name] = {"entity": name, "error": str(e),
                             "created": 0, "updated": 0}
    return {"ok": True, "configured": True, "results": results}


def sync_all_blocking(entities: list[str] | None = None) -> dict:
    """Sync entrypoint usable from a sync context (scheduler)."""
    return asyncio.run(sync_all(entities))
