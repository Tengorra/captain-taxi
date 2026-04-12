"""Health check endpoint."""

from fastapi import APIRouter
from services.redis_state import get_redis

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    try:
        r = await get_redis()
        await r.ping()
        redis_ok = True
    except Exception:
        redis_ok = False

    return {
        "status": "ok" if redis_ok else "degraded",
        "redis": "ok" if redis_ok else "error",
        "service": "captain-taxi-customer",
    }
