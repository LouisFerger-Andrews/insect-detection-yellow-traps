# SWD Insect Monitoring Platform

End-to-end local platform for monitoring *Drosophila suzukii* on yellow sticky traps.

## Repository Layout

This repository is organized into four top-level folders:

- `01_project_docs_notes/` -> documentation and notes
- `02_pm_analytics_dashboard/` -> internal Streamlit PM dashboard
- `03_application/` -> production app (backend, frontend, runtime model, compose files)
- `04_modeling_experimental/` -> CV/model experimentation (src, configs, data, runs, scripts, tests)

## Quickstart

### 1) Prerequisites

- Docker Desktop (or Docker Engine + Compose)
- Python `3.11+`
- Node.js `18+` (recommended `20+`)
- npm

### 2) Start databases

```bash
cd 03_application
docker compose -f docker-compose.yml up -d postgres neo4j
```

### 3) Start backend

```bash
cd 03_application/backend
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./scripts/start.sh
```

Backend URL: `http://localhost:8000`
Docs: `http://localhost:8000/docs`

### 4) Start frontend

```bash
cd 03_application/frontend
cp .env.example .env
npm install
npm run dev
```

Frontend URL: `http://localhost:5173`

### 5) PM analytics dashboard

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r 02_pm_analytics_dashboard/requirements.txt
streamlit run 02_pm_analytics_dashboard/app.py
```

## Modeling workflow

### CLI examples

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

PYTHONPATH=04_modeling_experimental/src .venv/bin/python -m cli list-approaches
PYTHONPATH=04_modeling_experimental/src .venv/bin/python -m cli prepare-data --project insect_yellow --approach yolo --config 04_modeling_experimental/configs/yolo.yaml
PYTHONPATH=04_modeling_experimental/src .venv/bin/python -m cli train --project insect_yellow --approach yolo --config 04_modeling_experimental/configs/yolo.yaml
PYTHONPATH=04_modeling_experimental/src .venv/bin/python -m cli evaluate --project insect_yellow --approach yolo --config 04_modeling_experimental/configs/yolo.yaml
```

### Strong YOLO script

```bash
./04_modeling_experimental/scripts/train_strong_yolo.sh
```

## Quality checks

```bash
./04_modeling_experimental/scripts/check_quality.sh
```

## Additional docs

- `REPO_STRUCTURE.md`
- `01_project_docs_notes/docs/standards/`
