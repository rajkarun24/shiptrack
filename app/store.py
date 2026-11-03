"""Temporary in-memory storage. In Sprint 2 we replace this with PostgreSQL."""
import uuid

from app.models import Parcel, ParcelCreate, Status


class ParcelStore:
    def __init__(self) -> None:
        self._parcels: dict[str, Parcel] = {}

    def create(self, data: ParcelCreate) -> Parcel:
        parcel = Parcel(id=uuid.uuid4().hex[:8], **data.model_dump())
        self._parcels[parcel.id] = parcel
        return parcel

    def get(self, parcel_id: str) -> Parcel | None:
        return self._parcels.get(parcel_id)

    def update_status(self, parcel_id: str, status: Status) -> Parcel | None:
        parcel = self._parcels.get(parcel_id)
        if parcel:
            parcel.status = status
        return parcel
