import logging
import secrets
from functools import lru_cache

from fastapi import Depends, FastAPI, Header, HTTPException

from app.cache import RedisCache
from app.config import Settings, get_settings
from app.events import EventPublishError, KafkaPublisher
from app.models import Parcel, ParcelCreate, StatusUpdate
from app.store import PostgresStore

settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("shiptrack")

app = FastAPI(title="ShipTrack API", version="0.3.0")


# Dependencies: built once, replaced by fakes in unit tests.
@lru_cache
def get_store() -> PostgresStore:
    return PostgresStore(get_settings().database_url)


@lru_cache
def get_cache() -> RedisCache:
    s = get_settings()
    return RedisCache(s.redis_url, s.cache_ttl_seconds)


@lru_cache
def get_publisher() -> KafkaPublisher:
    s = get_settings()
    return KafkaPublisher(s.kafka_bootstrap_servers, s.kafka_topic)


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
def ready(store=Depends(get_store), cache=Depends(get_cache),
          publisher=Depends(get_publisher)) -> dict:
    """Readiness: can the app actually serve traffic (database, cache, Kafka reachable)?"""
    checks = {"database": store.ping(), "cache": cache.ping(), "kafka": publisher.ping()}
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


@app.patch("/parcels/{parcel_id}/status", status_code=202,
           dependencies=[Depends(require_api_key)])
def update_status(parcel_id: str, update: StatusUpdate,
                  store=Depends(get_store), publisher=Depends(get_publisher)) -> dict:
    """Does NOT update the database. It publishes an event; the worker applies it.
    202 Accepted = 'received, will be processed', not 'done'."""
    if store.get(parcel_id) is None:
        raise HTTPException(status_code=404, detail="Parcel not found")
    try:
        event = publisher.publish_status(parcel_id, update.status)
    except EventPublishError as exc:
        logger.error("could not publish event: %s", exc)
        raise HTTPException(status_code=503, detail="Event queue unavailable") from exc
    logger.info("event %s queued: parcel %s -> %s", event.event_id, parcel_id, update.status.value)
    return {"message": "status update queued", "event_id": event.event_id,
            "parcel_id": parcel_id, "status": update.status.value}
