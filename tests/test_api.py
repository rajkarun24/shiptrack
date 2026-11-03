import os

# Set a fake key BEFORE the app loads. Tests never use real secrets.
os.environ["API_KEY"] = "test-key"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)
HEADERS = {"X-API-Key": "test-key"}
PARCEL = {"sender": "Asha", "recipient": "Ravi", "destination": "Hyderabad"}


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


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
