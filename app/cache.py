"""Redis cache for parcel lookups. Reads hit Redis first, the database second."""
import redis

from app.models import Parcel


class RedisCache:
    def __init__(self, url: str, ttl_seconds: int) -> None:
        self._r = redis.Redis.from_url(url, decode_responses=True)
        self._ttl = ttl_seconds

    @staticmethod
    def _key(parcel_id: str) -> str:
        return f"parcel:{parcel_id}"

    def get(self, parcel_id: str) -> Parcel | None:
        raw = self._r.get(self._key(parcel_id))
        return Parcel.model_validate_json(raw) if raw else None

    def set(self, parcel: Parcel) -> None:
        self._r.set(self._key(parcel.id), parcel.model_dump_json(), ex=self._ttl)

    def delete(self, parcel_id: str) -> None:
        self._r.delete(self._key(parcel_id))

    def ping(self) -> bool:
        try:
            return bool(self._r.ping())
        except redis.RedisError:
            return False
