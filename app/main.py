import logging
import secrets
from functools import lru_cache

from fastapi import Depends, FastAPI, Header, HTTPException

from app.cache import RedisCache
from app.config import Settings, get_settings
from app.models import Parcel, ParcelCreate, StatusUpdate
from app.store import PostgresStore

settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("shiptrack")

app = FastAPI(title="ShipTrack API", version="0.2.0")


# Dependencies: built once, replaced by fakes in unit tests.
@lru_cache
def get_store() -> PostgresStore:
    return PostgresStore(get_settings().database_url)


@lru_cache
def get_cache() -> RedisCache:
    s = get_settings()
    return RedisCache(s.redis_url, s.cache_ttl_seconds)


def require_api_key(
    x_api_key: str = Header(default=""),
    settings: Settings = Depends(get_settings),
) -> None:
    if not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


@app.get("/health")
def health() -> dict:
    """Liveness: is the process running? Never checks other services."""
    return {"status": "ok", "env": settings.app_env}


@app.get("/ready")
def ready(store=Depends(get_store), cache=Depends(get_cache)) -> dict:
    """Readiness: can the app actually serve traffic (database and cache reachable)?"""
    checks = {"database": store.ping(), "cache": cache.ping()}
    if not all(checks.values()):
        raise HTTPException(status_code=503, detail=checks)
    return {"status": "ready", **checks}


@app.post("/parcels", response_model=Parcel, status_code=201,
          dependencies=[Depends(require_api_key)])
def create_parcel(data: ParcelCreate, store=Depends(get_store)) -> Parcel:
    parcel = store.create(data)
    logger.info("parcel created id=%s", parcel.id)
    return parcel


@app.get("/parcels/{parcel_id}", response_model=Parcel)
def get_parcel(parcel_id: str, store=Depends(get_store), cache=Depends(get_cache)) -> Parcel:
    cached = cache.get(parcel_id)
    if cached:
        logger.info("cache HIT %s", parcel_id)
        return cached
    parcel = store.get(parcel_id)
    if parcel is None:
        raise HTTPException(status_code=404, detail="Parcel not found")
    logger.info("cache MISS %s", parcel_id)
    cache.set(parcel)
    return parcel


@app.patch("/parcels/{parcel_id}/status", response_model=Parcel,
           dependencies=[Depends(require_api_key)])
def update_status(parcel_id: str, update: StatusUpdate,
                  store=Depends(get_store), cache=Depends(get_cache)) -> Parcel:
    parcel = store.update_status(parcel_id, update.status)
    if parcel is None:
        raise HTTPException(status_code=404, detail="Parcel not found")
    cache.delete(parcel_id)   # data changed, so the cached copy is now stale
    logger.info("parcel %s -> %s", parcel_id, update.status.value)
    return parcel
