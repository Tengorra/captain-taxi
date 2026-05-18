"""
iCabbi sync trigger routes.

GET  /api/icabbi/status                — quick configured-or-not check
POST /api/icabbi/sync                  — run all syncs now
POST /api/icabbi/sync?entities=a,b     — run specific entities now
"""
from fastapi import APIRouter, Query
from typing import Optional

from ...services.icabbi_client import IcabbiClient
from ...services.icabbi_sync import sync_all, ENTITY_SYNCS

router = APIRouter(prefix="/icabbi", tags=["icabbi"])


@router.get("/status")
def status():
    return {
        "configured": IcabbiClient.is_configured(),
        "entities": list(ENTITY_SYNCS.keys()),
    }


@router.post("/sync")
async def trigger_sync(entities: Optional[str] = Query(None, description="CSV of entity names; empty = all")):
    names = [e.strip() for e in entities.split(",")] if entities else None
    return await sync_all(names)
