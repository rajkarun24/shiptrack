import os

# Fake values BEFORE the app loads. Tests never use real secrets or real services.
os.environ["API_KEY"] = "test-key"
os.environ["DATABASE_URL"] = "postgresql://fake:fake@localhost:5432/fake"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["KAFKA_BOOTSTRAP_SERVERS"] = "localhost:9092"

from fastapi.testclient import TestClient  # noqa: E402

from app.events import EventPublishError  # noqa: E402
from app.main import app, get_cache, get_publisher, get_store  # noqa: E402
from app.models import StatusEvent  # noqa: E402
from app.store import InMemoryStore  # noqa: E402
from app.worker import handle_message  # noqa: E402


class FakeCache:
    def __init__(self):
        self.data = {}

    def get(self, parcel_id):
        return self.data.get(parcel_id)

    def set(self, parcel):
        self.data[parcel.id] = parcel

    def delete(self, parcel_id):
        self.data.pop(parcel_id, None)

    def ping(self):
        return True


class FakePublisher:
    """Pretends to be Kafka: remembers events instead of sending them."""
    def __init__(self):
        self.events = []
        self.broken = False

    def publish_status(self, parcel_id, status):
        if self.broken:
            raise EventPublishError("broker down")
        event = StatusEvent(event_id=f"e{len(self.events)}", parcel_id=parcel_id, status=status)
        self.events.append(event)
        return event

    def ping(self):
        return True


store = InMemoryStore()
cache = FakeCache()
publisher = FakePublisher()
app.dependency_overrides[get_store] = lambda: store
app.dependency_overrides[get_cache] = lambda: cache
app.dependency_overrides[get_publisher] = lambda: publisher

client = TestClient(app)
HEADERS = {"X-API-Key": "test-key"}
PARCEL = {"sender": "Asha", "recipient": "Ravi", "destination": "Hyderabad"}


def new_parcel_id():
    return client.post("/parcels", json=PARCEL, headers=HEADERS).json()["id"]


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ready_checks_database_cache_and_kafka():
    body = client.get("/ready").json()
    assert body == {"status": "ready", "database": True, "cache": True, "kafka": True}


def test_create_requires_api_key():
    assert client.post("/parcels", json=PARCEL).status_code == 401
    assert client.post("/parcels", json=PARCEL,
                       headers={"X-API-Key": "wrong"}).status_code == 401


def test_create_and_get_parcel():
    r = client.post("/parcels", json=PARCEL, headers=HEADERS)
    assert r.status_code == 201
    parcel = r.json()
    assert parcel["status"] == "CREATED"
    r = client.get(f"/parcels/{parcel['id']}")
    assert r.status_code == 200
    assert r.json()["recipient"] == "Ravi"


def test_get_fills_cache():
    pid = new_parcel_id()
    client.get(f"/parcels/{pid}")
    assert pid in cache.data


def test_update_status_is_queued_not_applied():
    pid = new_parcel_id()
    r = client.patch(f"/parcels/{pid}/status", json={"status": "DELIVERED"}, headers=HEADERS)
    assert r.status_code == 202                      # accepted, not done
    assert publisher.events[-1].parcel_id == pid     # an event was published
    assert store.get(pid).status.value == "CREATED"  # database NOT changed by the API


def test_worker_applies_event_and_clears_cache():
    pid = new_parcel_id()
    client.get(f"/parcels/{pid}")                    # fills the cache
    client.patch(f"/parcels/{pid}/status", json={"status": "IN_TRANSIT"}, headers=HEADERS)
    raw = publisher.events[-1].model_dump_json().encode()
    assert handle_message(raw, store, cache) == "updated"
    assert store.get(pid).status.value == "IN_TRANSIT"
    assert pid not in cache.data


def test_worker_is_idempotent():
    """Kafka may deliver a message twice. Processing it twice must be harmless."""
    pid = new_parcel_id()
    client.patch(f"/parcels/{pid}/status", json={"status": "DELIVERED"}, headers=HEADERS)
    raw = publisher.events[-1].model_dump_json().encode()
    handle_message(raw, store, cache)
    handle_message(raw, store, cache)
    assert store.get(pid).status.value == "DELIVERED"


def test_worker_skips_malformed_and_unknown_parcel():
    assert handle_message(b"not json", store, cache) == "skipped"
    ghost = StatusEvent(event_id="x", parcel_id="ghost", status="DELIVERED")
    assert handle_message(ghost.model_dump_json().encode(), store, cache) == "skipped"


def test_update_returns_503_when_kafka_is_down():
    pid = new_parcel_id()
    publisher.broken = True
    try:
        r = client.patch(f"/parcels/{pid}/status", json={"status": "DELIVERED"}, headers=HEADERS)
        assert r.status_code == 503
    finally:
        publisher.broken = False


def test_invalid_status_rejected():
    pid = new_parcel_id()
    r = client.patch(f"/parcels/{pid}/status",
                     json={"status": "LOST_IN_SPACE"}, headers=HEADERS)
    assert r.status_code == 422


def test_unknown_parcel_404():
    assert client.get("/parcels/nope").status_code == 404
    r = client.patch("/parcels/nope/status", json={"status": "DELIVERED"}, headers=HEADERS)
    assert r.status_code == 404
