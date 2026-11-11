# ShipTrack

Parcel-tracking API built to practice a full DevOps pipeline (Docker, CI/CD, Terraform, Kubernetes, AWS).

## Run everything with Docker
```bash
cp .env.example .env     # then edit API_KEY and POSTGRES_PASSWORD
docker compose up --build
```
- API docs: http://localhost:8000/docs
- Liveness: `/health`   Readiness: `/ready`

Stop with `Ctrl+C`; remove containers with `docker compose down` (add `-v` to also delete the database volume).

## Unit tests and lint (no Docker needed)
```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
ruff check .
```
