import json
import redis.asyncio as aioredis
from typing import Optional
from config import get_settings

settings = get_settings()

_redis: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = await aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis


async def close_redis():
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


# ── Driver location helpers ────────────────────────────────────────────────


DRIVER_LOC_KEY = "driver:loc:{driver_id}"
DRIVER_STATUS_KEY = "driver:status:{driver_id}"


async def set_driver_location(driver_id: str, lat: float, lng: float, city: str):
    r = await get_redis()
    key = DRIVER_LOC_KEY.format(driver_id=driver_id)
    payload = json.dumps({"lat": lat, "lng": lng, "city": city})
    await r.setex(key, settings.driver_location_ttl, payload)
    # Also update the sorted set for geo queries
    await r.geoadd(f"drivers:geo:{city}", (lng, lat, driver_id))


async def get_driver_location(driver_id: str) -> Optional[dict]:
    r = await get_redis()
    key = DRIVER_LOC_KEY.format(driver_id=driver_id)
    data = await r.get(key)
    return json.loads(data) if data else None


async def set_driver_status(driver_id: str, status: str):
    r = await get_redis()
    key = DRIVER_STATUS_KEY.format(driver_id=driver_id)
    await r.setex(key, settings.driver_location_ttl * 2, status)


async def get_driver_status(driver_id: str) -> Optional[str]:
    r = await get_redis()
    key = DRIVER_STATUS_KEY.format(driver_id=driver_id)
    return await r.get(key)


async def find_nearby_drivers(
    city: str, lat: float, lng: float, radius_km: float, limit: int
) -> list[dict]:
    """Return drivers within radius_km of (lat, lng) in the given city."""
    r = await get_redis()
    geo_key = f"drivers:geo:{city}"
    results = await r.geosearch(
        geo_key,
        longitude=lng,
        latitude=lat,
        radius=radius_km,
        unit="km",
        sort="ASC",
        count=limit,
        withcoord=True,
        withdist=True,
    )
    drivers = []
    for item in results:
        driver_id, dist, (item_lng, item_lat) = item
        drivers.append(
            {
                "driver_id": driver_id,
                "distance_km": round(float(dist), 2),
                "lat": item_lat,
                "lng": item_lng,
            }
        )
    return drivers


# ── Assignment lock helpers ────────────────────────────────────────────────


async def acquire_assignment_lock(trip_id: str, ttl: int = 120) -> bool:
    """Prevent double-assignment. Returns True if lock acquired."""
    r = await get_redis()
    key = f"assign:lock:{trip_id}"
    return await r.set(key, "1", nx=True, ex=ttl)


async def release_assignment_lock(trip_id: str):
    r = await get_redis()
    await r.delete(f"assign:lock:{trip_id}")


# ── Pending assignment timeout queue ──────────────────────────────────────


PENDING_ASSIGNMENTS_KEY = "pending_assignments"


async def push_pending_assignment(trip_id: str, driver_id: str, deadline_ts: float):
    """Record a pending assignment so the timeout worker can re-assign."""
    r = await get_redis()
    payload = json.dumps({"trip_id": trip_id, "driver_id": driver_id})
    # Score = deadline epoch so we can pop expired ones cheaply
    await r.zadd(PENDING_ASSIGNMENTS_KEY, {payload: deadline_ts})


async def pop_expired_assignments(now_ts: float) -> list[dict]:
    r = await get_redis()
    items = await r.zrangebyscore(PENDING_ASSIGNMENTS_KEY, "-inf", now_ts)
    if items:
        await r.zremrangebyscore(PENDING_ASSIGNMENTS_KEY, "-inf", now_ts)
    return [json.loads(i) for i in items]
