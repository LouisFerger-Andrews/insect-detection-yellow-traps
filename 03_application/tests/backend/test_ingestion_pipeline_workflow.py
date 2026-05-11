from __future__ import annotations

from datetime import date
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api import analysis as analysis_api
from app.db.base import Base
from app.models import Detection, FieldMap, TrapUpload, User


@pytest.fixture()
def db_session(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite:///{tmp_path / 'ingestion.db'}")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        yield db
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def ingestion_user_and_field(db_session: Session) -> tuple[User, FieldMap]:
    user = User(
        id=101,
        email="grower@example.test",
        full_name="Grower",
        password_hash="not-used",
        role="user",
        is_active=True,
    )
    field = FieldMap(
        id="field-ingestion",
        owner_user_id=user.id,
        name="Ingestion Field",
        polygon_geojson='{"type":"Polygon","coordinates":[]}',
        area_m2=100.0,
    )
    db_session.add_all([user, field])
    db_session.commit()
    return user, field


def _upload(filename: str, content: bytes = b"fake-image-bytes") -> UploadFile:
    return UploadFile(filename=filename, file=BytesIO(content))


def test_upload_range_runs_ingestion_end_to_end(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    db_session: Session,
    ingestion_user_and_field: tuple[User, FieldMap],
) -> None:
    user, field = ingestion_user_and_field
    upload_dir = tmp_path / "uploads"
    graph_calls: list[tuple[str, int, date, int]] = []
    env_calls: list[tuple[str, date, date]] = []

    class FakeInferenceService:
        def run(self, image_path: Path):  # noqa: ANN201
            assert image_path.exists()
            return [
                {"bbox_xyxy": [1.0, 2.0, 3.0, 4.0], "confidence": 0.80, "class_id": 0},
                {"bbox_xyxy": [5.0, 6.0, 7.0, 8.0], "confidence": 0.60, "class_id": 1},
            ]

    class FakeGraphService:
        def link_upload_to_field(self, field_id: str, upload_id: int, capture_date: date, detection_count: int) -> None:
            graph_calls.append((field_id, upload_id, capture_date, detection_count))

        def close(self) -> None:
            graph_calls.append(("closed", 0, date.min, 0))

    def fake_sync_environment(db: Session, field_map: FieldMap, start: date, end: date) -> None:
        env_calls.append((field_map.id, start, end))

    monkeypatch.setattr(analysis_api, "get_settings", lambda: SimpleNamespace(upload_dir=str(upload_dir)))
    monkeypatch.setattr(analysis_api, "InferenceService", FakeInferenceService)
    monkeypatch.setattr(analysis_api, "GraphService", FakeGraphService)
    monkeypatch.setattr(analysis_api, "infer_sync_start_date", lambda db, field_id: date(2026, 1, 1))
    monkeypatch.setattr(analysis_api, "sync_environment_for_field", fake_sync_environment)

    response = analysis_api.upload_range(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 8),
        field_id=field.id,
        trap_id=None,
        trap_code="R01-P01",
        images=[_upload("trap-a.jpg"), _upload("trap-b.png")],
        db=db_session,
        current_user=user,
    )

    uploads = db_session.scalars(select(TrapUpload).order_by(TrapUpload.capture_date)).all()
    detections = db_session.scalars(select(Detection).order_by(Detection.upload_id, Detection.class_id)).all()
    saved_files = sorted(upload_dir.iterdir())

    assert response.total_images == 2
    assert [result.capture_date for result in response.results] == [date(2026, 1, 1), date(2026, 1, 8)]
    assert [result.detection_count for result in response.results] == [2, 2]
    assert [upload.trap_code for upload in uploads] == ["R01-P01", "R01-P01"]
    assert [upload.detection_count for upload in uploads] == [2, 2]
    assert [round(upload.confidence_avg, 2) for upload in uploads] == [0.70, 0.70]
    assert len(detections) == 4
    assert len(saved_files) == 2
    assert all(path.name.endswith(("_trap-a.jpg", "_trap-b.png")) for path in saved_files)
    assert graph_calls[:2] == [
        (field.id, uploads[0].id, date(2026, 1, 1), 2),
        (field.id, uploads[1].id, date(2026, 1, 8), 2),
    ]
    assert graph_calls[-1][0] == "closed"
    assert env_calls == [(field.id, date(2026, 1, 1), date.today())]


def test_upload_range_rejects_invalid_batch_before_storage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    db_session: Session,
    ingestion_user_and_field: tuple[User, FieldMap],
) -> None:
    user, field = ingestion_user_and_field
    upload_dir = tmp_path / "uploads"

    class UnexpectedInferenceService:
        def run(self, image_path: Path):  # noqa: ANN201
            raise AssertionError("inference should not run for an invalid batch")

    class FakeGraphService:
        def link_upload_to_field(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise AssertionError("graph linking should not run for an invalid batch")

        def close(self) -> None:
            return None

    monkeypatch.setattr(analysis_api, "get_settings", lambda: SimpleNamespace(upload_dir=str(upload_dir)))
    monkeypatch.setattr(analysis_api, "InferenceService", UnexpectedInferenceService)
    monkeypatch.setattr(analysis_api, "GraphService", FakeGraphService)

    with pytest.raises(HTTPException) as exc:
        analysis_api.upload_range(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 8),
            field_id=field.id,
            trap_id=None,
            trap_code="R01-P01",
            images=[_upload("capture-a.jpg"), _upload("training-sample.jpg")],
            db=db_session,
            current_user=user,
        )

    assert exc.value.status_code == 400
    assert "Training/validation/test dataset images are not allowed" in str(exc.value.detail)
    assert db_session.scalars(select(TrapUpload)).all() == []
    assert not upload_dir.exists()
