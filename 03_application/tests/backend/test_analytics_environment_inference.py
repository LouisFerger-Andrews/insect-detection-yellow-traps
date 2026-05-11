from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api import analytics as analytics_api
from app.api import environment as environment_api
from app.db.base import Base
from app.models import Detection, FieldMap, TrapUpload, User
from app.services.inference_service import InferenceService


@dataclass
class DummyUser:
    id: int
    role: str = "admin"


class FakeQuery:
    def __init__(
        self,
        *,
        all_value=None,
        first_value=None,
        one_value=None,
        scalar_value=None,
    ) -> None:
        self._all = all_value if all_value is not None else []
        self._first = first_value
        self._one = one_value
        self._scalar = scalar_value

    def join(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self

    def filter(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self

    def distinct(self):
        return self

    def order_by(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self

    def group_by(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self

    def limit(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self

    def with_entities(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self

    def all(self):
        return self._all

    def first(self):
        return self._first

    def one(self):
        return self._one

    def scalar(self):
        return self._scalar


class FakeDB:
    def __init__(self, queries: list[FakeQuery]) -> None:
        self._queries = list(queries)

    def query(self, *args, **kwargs):  # noqa: ANN002, ANN003
        if not self._queries:
            return FakeQuery()
        return self._queries.pop(0)


@pytest.fixture()
def insight_db_session(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite:///{tmp_path / 'insights.db'}")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        yield db
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def insight_seed_data(insight_db_session: Session) -> User:
    user = User(
        id=77,
        email="insights@example.test",
        full_name="Insight User",
        password_hash="not-used",
        role="user",
        is_active=True,
    )
    other_user = User(
        id=88,
        email="other-insights@example.test",
        full_name="Other User",
        password_hash="not-used",
        role="user",
        is_active=True,
    )
    field_a = FieldMap(
        id="field-a",
        owner_user_id=user.id,
        name="North Field",
        polygon_geojson="{}",
        area_m2=100.0,
    )
    field_b = FieldMap(
        id="field-b",
        owner_user_id=user.id,
        name="South Field",
        polygon_geojson="{}",
        area_m2=120.0,
    )
    hidden_field = FieldMap(
        id="hidden-field",
        owner_user_id=other_user.id,
        name="Hidden Field",
        polygon_geojson="{}",
        area_m2=80.0,
    )
    upload_a = TrapUpload(
        user_id=user.id,
        field_id=field_a.id,
        trap_id="trap-a",
        trap_code="T-A",
        capture_date=date(2026, 5, 1),
        image_path="storage/uploads/field-a/2026/05/01/T-A/a.jpg",
        detection_count=5,
        confidence_avg=0.82,
    )
    upload_b = TrapUpload(
        user_id=user.id,
        field_id=field_b.id,
        trap_id="trap-b",
        trap_code="T-B",
        capture_date=date(2026, 5, 2),
        image_path="storage/uploads/field-b/2026/05/02/T-B/b.jpg",
        detection_count=2,
        confidence_avg=0.61,
    )
    hidden_upload = TrapUpload(
        user_id=other_user.id,
        field_id=hidden_field.id,
        trap_id="trap-hidden",
        trap_code="T-H",
        capture_date=date(2026, 5, 3),
        image_path="storage/uploads/hidden-field/2026/05/03/T-H/h.jpg",
        detection_count=99,
        confidence_avg=0.95,
    )
    insight_db_session.add_all([user, other_user, field_a, field_b, hidden_field, upload_a, upload_b, hidden_upload])
    insight_db_session.flush()
    insight_db_session.add_all(
        [
            Detection(upload_id=upload_a.id, class_id=0, confidence=0.9, x1=1, y1=2, x2=3, y2=4),
            Detection(upload_id=upload_a.id, class_id=1, confidence=0.74, x1=5, y1=6, x2=7, y2=8),
            Detection(upload_id=upload_b.id, class_id=0, confidence=0.61, x1=10, y1=11, x2=12, y2=13),
            Detection(upload_id=hidden_upload.id, class_id=2, confidence=0.95, x1=20, y1=21, x2=22, y2=23),
        ]
    )
    insight_db_session.commit()
    return user


def test_analytics_overview_happy_path_admin() -> None:
    uploads_rows = [
        (SimpleNamespace(id=1, detection_count=5), SimpleNamespace(id="field-1", name="Field 1")),
        (SimpleNamespace(id=2, detection_count=3), SimpleNamespace(id="field-1", name="Field 1")),
    ]
    daily_rows = [SimpleNamespace(capture_date="2026-01-01", uploads=2, detections=8)]
    field_rows = [SimpleNamespace(field_id="field-1", field_name="Field 1", uploads=2, detections=8)]
    trap_rows = [SimpleNamespace(trap_code="R01-P01", uploads=2, detections=8)]
    db = FakeDB(
        [
            FakeQuery(all_value=[(2025,), (2026,)]),
            FakeQuery(all_value=uploads_rows),
            FakeQuery(all_value=daily_rows),
            FakeQuery(all_value=field_rows),
            FakeQuery(all_value=trap_rows),
        ]
    )

    out = analytics_api.analytics_overview(
        field_id=None,
        year=None,
        db=db,
        current_user=DummyUser(id=1, role="admin"),
    )
    assert out["scope"] == "all-fields"
    assert out["totals"]["uploads"] == 2
    assert out["totals"]["detections"] == 8
    assert out["totals"]["avg_detection_per_upload"] == 4.0
    assert out["available_years"] == [2025, 2026]
    assert out["by_trap"][0]["trap_code"] == "R01-P01"


def test_analytics_overview_field_not_found() -> None:
    db = FakeDB([FakeQuery(all_value=[]), FakeQuery(first_value=None)])
    with pytest.raises(HTTPException) as exc:
        analytics_api.analytics_overview(
            field_id="missing",
            year=None,
            db=db,
            current_user=DummyUser(id=2, role="user"),
        )
    assert exc.value.status_code == 404


def test_insight_dashboard_filters_kpis_results_and_predictions(
    insight_db_session: Session,
    insight_seed_data: User,
) -> None:
    out = analytics_api.insight_dashboard(
        field_id=None,
        trap_code=None,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 2),
        min_detections=2,
        max_detections=5,
        min_confidence=0.6,
        db=insight_db_session,
        current_user=insight_seed_data,
    )

    assert out["context"]["scope"] == "owned-fields"
    assert out["context"]["dataset_version"] == "metadata-v1.0.0"
    assert out["kpis"]["processed_images"] == 2
    assert out["kpis"]["total_detections"] == 7
    assert out["kpis"]["avg_detections_per_image"] == 3.5
    assert out["kpis"]["highest_activity_field"]["field_name"] == "North Field"
    assert out["kpis"]["highest_activity_trap"]["trap_code"] == "T-A"
    assert [row["capture_date"] for row in out["trend"]] == ["2026-05-01", "2026-05-02"]
    assert {row["field_id"] for row in out["comparisons"]["by_field"]} == {"field-a", "field-b"}
    assert [row["upload_id"] for row in out["results"]] == [2, 1]
    assert out["results"][1]["detections"][0]["bbox_xyxy"] == [1.0, 2.0, 3.0, 4.0]
    assert all(result["field_id"] != "hidden-field" for result in out["results"])


def test_insight_dashboard_csv_export_includes_context_and_rows(
    insight_db_session: Session,
    insight_seed_data: User,
) -> None:
    response = analytics_api.export_insight_dashboard_csv(
        field_id="field-a",
        trap_code="T-A",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 1),
        min_detections=1,
        max_detections=5,
        min_confidence=0.7,
        db=insight_db_session,
        current_user=insight_seed_data,
    )

    text = response.body.decode("utf-8")
    assert "dataset_version,metadata-v1.0.0" in text
    assert "filter_field_id,field-a" in text
    assert "filter_max_detections,5" in text
    assert "filter_min_confidence,0.7" in text
    assert "upload_id,image_path,field_id,field_name,trap_id,trap_code,capture_date,detection_count,confidence_avg,prediction_count,prediction_metadata" in text
    assert "North Field" in text
    assert "class=0 conf=0.9000" in text


def test_environment_get_field_or_403_and_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    field = SimpleNamespace(id="field-1", name="Field 1", owner_user_id=7)
    db = FakeDB([FakeQuery(first_value=field)])
    out = environment_api._get_field_or_403(db, "field-1", DummyUser(id=7, role="user"))
    assert out.id == "field-1"

    db_forbidden = FakeDB([FakeQuery(first_value=field)])
    with pytest.raises(HTTPException) as exc:
        environment_api._get_field_or_403(db_forbidden, "field-1", DummyUser(id=8, role="user"))
    assert exc.value.status_code == 403

    db_sync = FakeDB([FakeQuery(first_value=field)])
    monkeypatch.setattr(
        environment_api,
        "infer_sync_start_date",
        lambda db, fid: __import__("datetime").date(2026, 1, 1),
    )
    monkeypatch.setattr(
        environment_api,
        "infer_sync_end_date",
        lambda db, fid: __import__("datetime").date(2026, 1, 31),
    )
    monkeypatch.setattr(
        environment_api,
        "sync_environment_for_field",
        lambda db, f, s, e: {"inserted_or_updated": 3, "sources": {}},
    )
    synced = environment_api.sync_field_environment("field-1", {}, db_sync, DummyUser(id=7, role="user"))
    assert synced["field_id"] == "field-1"
    assert synced["inserted_or_updated"] == 3


def test_environment_overview_and_timeseries() -> None:
    field = SimpleNamespace(id="field-1", name="Field 1", owner_user_id=1, created_at="2026-01-01")
    env_summary = SimpleNamespace(records=5, start_date="2026-01-01", end_date="2026-01-05", last_fetch_at=None)
    latest = SimpleNamespace(
        observation_date="2026-01-05",
        temperature_mean_c=10.0,
        precipitation_mm=2.0,
        gdd_base10_c=1.1,
        water_deficit_mm=0.3,
    )
    pop_rows = [SimpleNamespace(week_start="2026-01-01", uploads=2, avg_population=1.5, total_population=3)]
    trap_rows = [SimpleNamespace(week_start="2026-01-01", trap_code="R01-P01", uploads=2, avg_population=1.5, total_population=3)]
    weather_rows = [SimpleNamespace(week_start="2026-01-01", temp_avg=9.0, rain_sum=1.0, gdd_avg=0.5, deficit_avg=0.2, heat_stress_avg=0.0)]

    db_overview = FakeDB(
        [
            FakeQuery(all_value=[field]),
            FakeQuery(all_value=[SimpleNamespace(year=2026)]),
            FakeQuery(one_value=env_summary),
            FakeQuery(first_value=latest),
            FakeQuery(all_value=[("open-meteo", 5)]),
        ]
    )
    out = environment_api.environment_overview(db=db_overview, current_user=DummyUser(id=1, role="admin"))
    assert out["available_years"] == [2026]
    assert out["fields"][0]["field_id"] == "field-1"

    db_timeseries = FakeDB(
        [
            FakeQuery(first_value=field),
            FakeQuery(scalar_value=date(2026, 1, 15)),  # upload query (max/min)
            FakeQuery(scalar_value=date(2026, 1, 14)),  # environment query (max/min)
            FakeQuery(all_value=pop_rows),
            FakeQuery(all_value=trap_rows),
            FakeQuery(all_value=weather_rows),
        ]
    )
    series = environment_api.environment_field_timeseries(
        field_id="field-1",
        weeks=2,
        all_data=False,
        year=None,
        db=db_timeseries,
        current_user=DummyUser(id=1, role="admin"),
    )
    assert series["field_id"] == "field-1"
    assert len(series["population_weekly"]) == 1
    assert len(series["trap_weekly"]) == 1
    assert len(series["weather_weekly"]) == 1


def test_inference_service_get_model_and_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    weights = tmp_path / "model.pt"
    weights.write_text("mock")
    image = tmp_path / "image.jpg"
    image.write_bytes(b"fake-image")

    class FakeBox:
        def __init__(self) -> None:
            self.xyxy = [SimpleNamespace(tolist=lambda: [1.0, 2.0, 3.0, 4.0])]
            self.conf = [0.91]
            self.cls = [2]

    class FakeResult:
        def __init__(self) -> None:
            self.boxes = [FakeBox()]

    class FakeModel:
        def predict(self, **kwargs):  # noqa: ANN003
            return [FakeResult()]

    monkeypatch.setattr(
        "app.services.inference_service.get_settings",
        lambda: SimpleNamespace(model_weights_path=str(weights), model_image_size=640, model_confidence=0.25),
    )
    monkeypatch.setattr("app.services.inference_service.YOLO", lambda path: FakeModel())

    svc = InferenceService()
    out = svc.run(image)
    assert out[0]["class_id"] == 2
    assert out[0]["confidence"] == 0.91
    assert out[0]["bbox_xyxy"] == [1.0, 2.0, 3.0, 4.0]
