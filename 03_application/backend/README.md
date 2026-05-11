# SWD Monitoring Backend

FastAPI backend for:
- Authentication and role-based access (PostgreSQL)
- Field graph and relationships (Neo4j)
- Sticky trap image upload and YOLO PoC inference
- Map-based field polygons and trap points (OpenStreetMap/Nominatim)

## 1) Configure

```bash
cd 03_application/backend
cp .env.example .env
```

Generate a secure `SECRET_KEY` in `.env`.

## 2) Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3) Start databases

From repository root:

```bash
docker compose up -d postgres neo4j
```

## 4) Run API

```bash
cd 03_application/backend
source .venv/bin/activate
./scripts/start.sh
```

API docs: `http://localhost:8000/docs`

## Seeded admin user

At startup the API creates an admin user and sample graph field if missing.

Default credentials (change in `.env`):
- email: `admin@swd-monitoring.com`
- password: `Admin123ChangeMe`

## Important model path

`MODEL_WEIGHTS_PATH` defaults to:

`../poc-model/swd_yolo_best.pt`

This points to the copied PoC checkpoint from your previous run.

## New map workflow endpoints

- `GET /api/map/search?q=...` search farm/location (Nominatim)
- `POST /api/map/fields` create field polygon and initial trap points
- `GET /api/map/fields` list saved map fields
- `GET /api/map/fields/{field_id}` get full polygon + traps
- `POST /api/map/fields/{field_id}/traps` add trap by clicking map

`/api/analysis/upload-range` now supports `trap_id` so uploads can be attached to exact map trap locations.
