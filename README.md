# ShipTrack

Parcel-tracking API built to practice a full DevOps pipeline (Docker, CI/CD, Terraform, Kubernetes, AWS).

## Run locally
```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env        # then edit API_KEY
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000/docs

## Test and lint
```bash
pytest
ruff check .
```
