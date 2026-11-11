"""Storage layer.

InMemoryStore: used by unit tests (no database needed).
PostgresStore: used for real, talks to PostgreSQL.
Both have the same methods, so the API code doesn't care which one it gets.
"""
import uuid

import psycopg
from psycopg.rows import dict_row

from app.models import Parcel, ParcelCreate, Status


class InMemoryStore:
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

    def ping(self) -> bool:
        return True


class PostgresStore:
    def __init__(self, database_url: str) -> None:
        self._url = database_url
        self._init_schema()

    def _connect(self):
        return psycopg.connect(self._url, row_factory=dict_row)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS parcels (
                    id          TEXT PRIMARY KEY,
                    sender      TEXT NOT NULL,
                    recipient   TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    status      TEXT NOT NULL DEFAULT 'CREATED'
                )
                """
            )

    def create(self, data: ParcelCreate) -> Parcel:
        parcel = Parcel(id=uuid.uuid4().hex[:8], **data.model_dump())
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO parcels (id, sender, recipient, destination, status) "
                "VALUES (%s, %s, %s, %s, %s)",
                (parcel.id, parcel.sender, parcel.recipient, parcel.destination,
                 parcel.status.value),
            )
        return parcel

    def get(self, parcel_id: str) -> Parcel | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM parcels WHERE id = %s", (parcel_id,)).fetchone()
        return Parcel(**row) if row else None

    def update_status(self, parcel_id: str, status: Status) -> Parcel | None:
        with self._connect() as conn:
            row = conn.execute(
                "UPDATE parcels SET status = %s WHERE id = %s RETURNING *",
                (status.value, parcel_id),
            ).fetchone()
        return Parcel(**row) if row else None

    def ping(self) -> bool:
        try:
            with self._connect() as conn:
                conn.execute("SELECT 1")
            return True
        except psycopg.Error:
            return False
