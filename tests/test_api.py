import os

# Fake values BEFORE the app loads. Tests never use real secrets or real services.
os.environ["API_KEY"] = "test-key"
os.environ["DATABASE_URL"] = "postgresql://fake:fake@localhost:5432/fake"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app, get_cache, get_store  # noqa: E402
from app.store import InMemoryStore  # noqa: E402


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


store = InMemoryStore()
cache = FakeCache()
app.dependency_overrides[get_store] = lambda: store
app.dependency_overrides[get_cache] = lambda: cache

client = TestClient(app)
HEADERS = {"X-API-Key": "test-key"}
PARCEL = {"sender": "Asha", "recipient": "Ravi", "destination": "Hyderabad"}


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ready():
    assert client.get("/ready").json()["status"] == "ready"


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


def test_get_fills_cache_and_update_clears_it():
    pid = client.post("/parcels", json=PARCEL, headers=HEADERS).json()["id"]
    client.get(f"/parcels/{pid}")
    assert pid in cache.data
    client.patch(f"/parcels/{pid}/status", json={"status": "IN_TRANSIT"}, headers=HEADERS)
    assert pid not in cache.data
    assert client.get(f"/parcels/{pid}").json()["status"] == "IN_TRANSIT"


def test_update_status():
    pid = client.post("/parcels", json=PARCEL, headers=HEADERS).json()["id"]
    r = client.patch(f"/parcels/{pid}/status",
                     json={"status": "DELIVERED"}, headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["status"] == "DELIVERED"


def test_invalid_status_rejected():
    pid = client.post("/parcels", json=PARCEL, headers=HEADERS).json()["id"]
    r = client.patch(f"/parcels/{pid}/status",
                     json={"status": "LOST_IN_SPACE"}, headers=HEADERS)
    assert r.status_code == 422


def test_unknown_parcel_404():
    assert client.get("/parcels/nope").status_code == 404
