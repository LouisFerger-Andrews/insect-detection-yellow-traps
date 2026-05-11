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
from app.models import Detection, FieldMap, TrapPoint, TrapUpload, User


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


JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"fake-image-bytes"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake-image-bytes"


def _upload(filename: str, content: bytes | None = None) -> UploadFile:
    if content is None:
        content = PNG_BYTES if filename.lower().endswith(".png") else JPEG_BYTES
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
    saved_files = sorted(path for path in upload_dir.rglob("*") if path.is_file())

    assert response.total_images == 2
    assert [result.capture_date for result in response.results] == [date(2026, 1, 1), date(2026, 1, 8)]
    assert [result.detection_count for result in response.results] == [2, 2]
    assert [upload.trap_code for upload in uploads] == ["R01-P01", "R01-P01"]
    assert [upload.detection_count for upload in uploads] == [2, 2]
    assert [round(upload.confidence_avg, 2) for upload in uploads] == [0.70, 0.70]
    assert len(detections) == 4
    assert len(saved_files) == 2
    assert all(path.name.endswith(("_trap-a.jpg", "_trap-b.png")) for path in saved_files)
    assert saved_files[0].parts[-6:-1] == ("field-ingestion", "2026", "01", "01", "R01-P01")
    assert saved_files[1].parts[-6:-1] == ("field-ingestion", "2026", "01", "08", "R01-P01")
    assert [Path(upload.image_path) for upload in uploads] == saved_files
    assert graph_calls[:2] == [
        (field.id, uploads[0].id, date(2026, 1, 1), 2),
        (field.id, uploads[1].id, date(2026, 1, 8), 2),
    ]
    assert graph_calls[-1][0] == "closed"
    assert env_calls == [(field.id, date(2026, 1, 1), date.today())]


def test_upload_range_persists_structured_exact_trap_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    db_session: Session,
    ingestion_user_and_field: tuple[User, FieldMap],
) -> None:
    user, field = ingestion_user_and_field
    trap = TrapPoint(
        id="trap-structured",
        field_id=field.id,
        code="R02-P04",
        custom_name="North Edge",
        latitude=52.0,
        longitude=5.0,
        row_index=2,
        position_index=4,
    )
    db_session.add(trap)
    db_session.commit()
    upload_dir = tmp_path / "uploads"
    graph_calls: list[tuple[str, int, date, int]] = []

    class FakeInferenceService:
        def run(self, image_path: Path):  # noqa: ANN201
            assert image_path.exists()
            return [{"bbox_xyxy": [10.0, 20.0, 30.0, 40.0], "confidence": 0.75, "class_id": 1}]

    class FakeGraphService:
        def link_upload_to_field(self, field_id: str, upload_id: int, capture_date: date, detection_count: int) -> None:
            graph_calls.append((field_id, upload_id, capture_date, detection_count))

        def close(self) -> None:
            return None

    monkeypatch.setattr(analysis_api, "get_settings", lambda: SimpleNamespace(upload_dir=str(upload_dir)))
    monkeypatch.setattr(analysis_api, "InferenceService", FakeInferenceService)
    monkeypatch.setattr(analysis_api, "GraphService", FakeGraphService)
    monkeypatch.setattr(analysis_api, "infer_sync_start_date", lambda db, field_id: None)

    response = analysis_api.upload_range(
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 1),
        field_id=field.id,
        trap_id=trap.id,
        trap_code="North Edge",
        images=[_upload("structured-trap.jpg")],
        db=db_session,
        current_user=user,
    )

    upload = db_session.scalars(select(TrapUpload)).one()
    detection = db_session.scalars(select(Detection)).one()

    assert response.total_images == 1
    assert response.results[0].field_id == field.id
    assert response.results[0].trap_code == "North Edge"
    assert upload.field_id == field.id
    assert upload.trap_id == trap.id
    assert upload.trap_code == "North Edge"
    assert upload.capture_date == date(2026, 5, 1)
    assert Path(upload.image_path).parts[-6:-1] == ("field-ingestion", "2026", "05", "01", "North-Edge")
    assert Path(upload.image_path).exists()
    assert upload.detection_count == 1
    assert round(upload.confidence_avg, 2) == 0.75
    assert detection.upload_id == upload.id
    assert graph_calls == [(field.id, upload.id, date(2026, 5, 1), 1)]


def test_get_upload_prediction_result_returns_image_metadata_and_detections(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    db_session: Session,
    ingestion_user_and_field: tuple[User, FieldMap],
) -> None:
    user, field = ingestion_user_and_field
    upload_dir = tmp_path / "uploads"

    class FakeInferenceService:
        def run(self, image_path: Path):  # noqa: ANN201
            assert image_path.exists()
            return [
                {"bbox_xyxy": [1.0, 2.0, 3.0, 4.0], "confidence": 0.8, "class_id": 0},
                {"bbox_xyxy": [5.0, 6.0, 7.0, 8.0], "confidence": 0.6, "class_id": 2},
            ]

    class FakeGraphService:
        def link_upload_to_field(self, *args, **kwargs):  # noqa: ANN002, ANN003
            return None

        def close(self) -> None:
            return None

    monkeypatch.setattr(analysis_api, "get_settings", lambda: SimpleNamespace(upload_dir=str(upload_dir)))
    monkeypatch.setattr(analysis_api, "InferenceService", FakeInferenceService)
    monkeypatch.setattr(analysis_api, "GraphService", FakeGraphService)
    monkeypatch.setattr(analysis_api, "infer_sync_start_date", lambda db, field_id: None)

    upload_response = analysis_api.upload_range(
        start_date=date(2026, 5, 2),
        end_date=date(2026, 5, 2),
        field_id=field.id,
        trap_id=None,
        trap_code="FIELD_BATCH",
        images=[_upload("prediction-detail.jpg")],
        db=db_session,
        current_user=user,
    )

    detail = analysis_api.get_upload_prediction_result(
        upload_response.results[0].upload_id,
        db=db_session,
        current_user=user,
    )

    assert detail.id == upload_response.results[0].upload_id
    assert detail.field_id == field.id
    assert detail.trap_id is None
    assert detail.trap_code == "FIELD_BATCH"
    assert detail.capture_date == date(2026, 5, 2)
    assert detail.image_path.endswith("_prediction-detail.jpg")
    assert detail.detection_count == 2
    assert round(detail.confidence_avg, 2) == 0.70
    assert [d.class_id for d in detail.detections] == [0, 2]
    assert [d.confidence for d in detail.detections] == [0.8, 0.6]
    assert [d.bbox_xyxy for d in detail.detections] == [[1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]]


def test_get_upload_prediction_result_enforces_upload_ownership(
    db_session: Session,
    ingestion_user_and_field: tuple[User, FieldMap],
) -> None:
    owner, field = ingestion_user_and_field
    upload = TrapUpload(
        user_id=owner.id,
        field_id=field.id,
        trap_id=None,
        trap_code="FIELD_BATCH",
        capture_date=date(2026, 5, 2),
        image_path="storage/uploads/field/2026/05/02/FIELD_BATCH/example.jpg",
        detection_count=0,
        confidence_avg=0.0,
    )
    db_session.add(upload)
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        analysis_api.get_upload_prediction_result(
            upload.id,
            db=db_session,
            current_user=User(id=202, email="other@example.test", full_name="Other", password_hash="not-used", role="user"),
        )

    assert exc.value.status_code == 404


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


def test_upload_range_rejects_oversized_batch_before_processing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    db_session: Session,
    ingestion_user_and_field: tuple[User, FieldMap],
) -> None:
    user, field = ingestion_user_and_field

    class UnexpectedInferenceService:
        def run(self, image_path: Path):  # noqa: ANN201
            raise AssertionError("inference should not run for oversized batches")

    monkeypatch.setattr(analysis_api, "get_settings", lambda: SimpleNamespace(upload_dir=str(tmp_path / "uploads")))
    monkeypatch.setattr(analysis_api, "InferenceService", UnexpectedInferenceService)

    with pytest.raises(HTTPException) as exc:
        analysis_api.upload_range(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 8),
            field_id=field.id,
            trap_id=None,
            trap_code="FIELD_BATCH",
            images=[_upload(f"capture-{idx}.jpg") for idx in range(51)],
            db=db_session,
            current_user=user,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "A batch can contain at most 50 images"
    assert db_session.scalars(select(TrapUpload)).all() == []


def test_upload_range_rolls_back_sql_when_batch_processing_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    db_session: Session,
    ingestion_user_and_field: tuple[User, FieldMap],
) -> None:
    user, field = ingestion_user_and_field
    upload_dir = tmp_path / "uploads"
    seen: list[str] = []

    class FailingInferenceService:
        def run(self, image_path: Path):  # noqa: ANN201
            seen.append(image_path.name)
            if len(seen) == 2:
                raise RuntimeError("model failed")
            return [{"bbox_xyxy": [1.0, 2.0, 3.0, 4.0], "confidence": 0.8, "class_id": 0}]

    class FakeGraphService:
        def link_upload_to_field(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise AssertionError("graph linking should not run when processing fails")

        def close(self) -> None:
            return None

    monkeypatch.setattr(analysis_api, "get_settings", lambda: SimpleNamespace(upload_dir=str(upload_dir)))
    monkeypatch.setattr(analysis_api, "InferenceService", FailingInferenceService)
    monkeypatch.setattr(analysis_api, "GraphService", FakeGraphService)

    with pytest.raises(HTTPException) as exc:
        analysis_api.upload_range(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 2),
            field_id=field.id,
            trap_id=None,
            trap_code="FIELD_BATCH",
            images=[_upload("capture-a.jpg"), _upload("capture-b.jpg")],
            db=db_session,
            current_user=user,
        )

    assert exc.value.status_code == 500
    assert db_session.scalars(select(TrapUpload)).all() == []
    assert db_session.scalars(select(Detection)).all() == []


def test_upload_range_uses_explicit_capture_dates_for_per_image_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    db_session: Session,
    ingestion_user_and_field: tuple[User, FieldMap],
) -> None:
    user, field = ingestion_user_and_field
    upload_dir = tmp_path / "uploads"
    graph_calls: list[tuple[str, int, date, int]] = []

    class FakeInferenceService:
        def run(self, image_path: Path):  # noqa: ANN201
            assert image_path.exists()
            return [{"bbox_xyxy": [1.0, 2.0, 3.0, 4.0], "confidence": 0.9, "class_id": 0}]

    class FakeGraphService:
        def link_upload_to_field(self, field_id: str, upload_id: int, capture_date: date, detection_count: int) -> None:
            graph_calls.append((field_id, upload_id, capture_date, detection_count))

        def close(self) -> None:
            return None

    monkeypatch.setattr(analysis_api, "get_settings", lambda: SimpleNamespace(upload_dir=str(upload_dir)))
    monkeypatch.setattr(analysis_api, "InferenceService", FakeInferenceService)
    monkeypatch.setattr(analysis_api, "GraphService", FakeGraphService)
    monkeypatch.setattr(analysis_api, "infer_sync_start_date", lambda db, field_id: None)

    response = analysis_api.upload_range(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 8),
        field_id=field.id,
        trap_id=None,
        trap_code="FIELD_BATCH",
        capture_dates=[date(2026, 1, 3), date(2026, 1, 6)],
        images=[_upload("capture-a.jpg"), _upload("capture-b.jpg")],
        db=db_session,
        current_user=user,
    )

    uploads = db_session.scalars(select(TrapUpload).order_by(TrapUpload.capture_date)).all()

    assert [result.capture_date for result in response.results] == [date(2026, 1, 3), date(2026, 1, 6)]
    assert [upload.capture_date for upload in uploads] == [date(2026, 1, 3), date(2026, 1, 6)]
    assert [upload.trap_id for upload in uploads] == [None, None]
    assert [upload.field_id for upload in uploads] == [field.id, field.id]
    assert [upload.trap_code for upload in uploads] == ["FIELD_BATCH", "FIELD_BATCH"]
    assert [call[2] for call in graph_calls] == [date(2026, 1, 3), date(2026, 1, 6)]


def test_upload_range_rejects_inconsistent_per_image_capture_dates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
    ingestion_user_and_field: tuple[User, FieldMap],
) -> None:
    user, field = ingestion_user_and_field

    class UnexpectedInferenceService:
        def run(self, image_path: Path):  # noqa: ANN201
            raise AssertionError("inference should not run for inconsistent per-image metadata")

    monkeypatch.setattr(analysis_api, "get_settings", lambda: SimpleNamespace(upload_dir=str(tmp_path / "uploads")))
    monkeypatch.setattr(analysis_api, "InferenceService", UnexpectedInferenceService)

    with pytest.raises(HTTPException) as exc:
        analysis_api.upload_range(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 8),
            field_id=field.id,
            trap_id=None,
            trap_code="FIELD_BATCH",
            capture_dates=[date(2026, 1, 3)],
            images=[_upload("capture-a.jpg"), _upload("capture-b.jpg")],
            db=db_session,
            current_user=user,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "capture_dates must contain exactly one date for each uploaded image"
    assert db_session.scalars(select(TrapUpload)).all() == []


def test_upload_range_rejects_inconsistent_trap_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    db_session: Session,
    ingestion_user_and_field: tuple[User, FieldMap],
) -> None:
    user, field = ingestion_user_and_field
    trap = TrapPoint(
        id="trap-1",
        field_id=field.id,
        code="R01-P01",
        custom_name=None,
        latitude=52.0,
        longitude=5.0,
        row_index=1,
        position_index=1,
    )
    db_session.add(trap)
    db_session.commit()

    class UnexpectedInferenceService:
        def run(self, image_path: Path):  # noqa: ANN201
            raise AssertionError("inference should not run for inconsistent metadata")

    class FakeGraphService:
        def close(self) -> None:
            return None

    monkeypatch.setattr(analysis_api, "get_settings", lambda: SimpleNamespace(upload_dir=str(tmp_path / "uploads")))
    monkeypatch.setattr(analysis_api, "InferenceService", UnexpectedInferenceService)
    monkeypatch.setattr(analysis_api, "GraphService", FakeGraphService)

    with pytest.raises(HTTPException) as exc:
        analysis_api.upload_range(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 1),
            field_id="field-other",
            trap_id=trap.id,
            trap_code=trap.code,
            images=[_upload("capture-a.jpg")],
            db=db_session,
            current_user=user,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "field_id does not match selected trap"
    assert db_session.scalars(select(TrapUpload)).all() == []
