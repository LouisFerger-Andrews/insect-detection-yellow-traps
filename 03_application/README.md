# 03 Application

Production application components live here.

## Contents

- `backend/` -> FastAPI backend
- `frontend/` -> React frontend
- `poc-model/` -> model artifacts consumed by backend
- `docker-compose.yml` -> Postgres + Neo4j
- `docker-compose.app.yml` -> backend + frontend services

## Run backend

```bash
cd 03_application/backend
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./scripts/start.sh
```

## Run frontend

```bash
cd 03_application/frontend
cp .env.example .env
npm install
npm run dev
```
