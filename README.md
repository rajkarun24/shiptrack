# ShipTrack

Parcel-tracking system built to practice a full DevOps pipeline (Docker, CI/CD, Terraform, Kubernetes, AWS).

## Architecture (local)
```
Client -> API (FastAPI) -> PostgreSQL
              |        \-> Redis (read cache)
              v
        Kafka topic "parcel-status" -> Worker -> PostgreSQL (+ clears Redis cache)
```
`PATCH /parcels/{id}/status` publishes an event and returns **202 Accepted**; the worker applies it.

## Run everything with Docker
```bash
cp .env.example .env     # then edit API_KEY and POSTGRES_PASSWORD
docker compose up --build
```
- API docs: http://localhost:8000/docs
- Liveness: `/health`   Readiness: `/ready` (database, cache, Kafka)

Stop with `Ctrl+C`; `docker compose down` removes containers (add `-v` to also delete database and Kafka data).

## Unit tests and lint (no Docker needed)
```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
ruff check .
```
