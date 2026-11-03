import logging
import secrets

from fastapi import Depends, FastAPI, Header, HTTPException

from app.config import Settings, get_settings
from app.models import Parcel, ParcelCreate, StatusUpdate
from app.store import ParcelStore

settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("shiptrack")

app = FastAPI(title="ShipTrack API", version="0.1.0")
store = ParcelStore()


def require_api_key(
    x_api_key: str = Header(default=""),
    settings: Settings = Depends(get_settings),
) -> None:
    # compare_digest avoids timing attacks when comparing secrets
    if not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


@app.get("/health")
def health() -> dict:
    """Load balancers and Kubernetes call this to check the app is alive."""
    return {"status": "ok", "env": settings.app_env}


@app.post("/parcels", response_model=Parcel, status_code=201,
          dependencies=[Depends(require_api_key)])
def create_parcel(data: ParcelCreate) -> Parcel:
    parcel = store.create(data)
    logger.info("parcel created id=%s", parcel.id)
    return parcel


@app.get("/parcels/{parcel_id}", response_model=Parcel)
def get_parcel(parcel_id: str) -> Parcel:
    parcel = store.get(parcel_id)
    if parcel is None:
        raise HTTPException(status_code=404, detail="Parcel not found")
    return parcel


@app.patch("/parcels/{parcel_id}/status", response_model=Parcel,
           dependencies=[Depends(require_api_key)])
def update_status(parcel_id: str, update: StatusUpdate) -> Parcel:
    parcel = store.update_status(parcel_id, update.status)
    if parcel is None:
        raise HTTPException(status_code=404, detail="Parcel not found")
    logger.info("parcel %s -> %s", parcel_id, update.status.value)
    return parcel
