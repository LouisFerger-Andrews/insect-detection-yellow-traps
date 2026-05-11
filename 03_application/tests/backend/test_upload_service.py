from __future__ import annotations

from datetime import date
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")

from app.services.upload_service import (
    allocate_capture_dates,
    build_upload_storage_path,
    normalize_optional_text,
    save_upload_file,
    secure_filename,
    validate_identifier,
    validate_trap_code,
    validate_upload_file,
)

JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"jpeg-bytes"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"png-bytes"
WEBP_BYTES = b"RIFF\x10\x00\x00\x00WEBP" + b"webp-bytes"


def test_secure_filename_strips_unsafe_chars() -> None:
    assert secure_filename("..//bad*name?.jpg") == "badname.jpg"
    assert secure_filename("") == "image.jpg"


def test_allocate_capture_dates_spreads_evenly() -> None:
    start = date(2026, 1, 1)
    end = date(2026, 1, 11)
    values = allocate_capture_dates(start, end, 3)
    assert values == [date(2026, 1, 1), date(2026, 1, 6), date(2026, 1, 11)]


def test_save_upload_file_persists_content(tmp_path: Path) -> None:
    content = b"abc123"
    upload = SimpleNamespace(filename="trap.jpg", file=BytesIO(content))
    saved = save_upload_file(tmp_path, upload)
    assert saved.exists()
    assert saved.read_bytes() == content
    assert saved.name.endswith("_trap.jpg")


def test_save_upload_file_uses_hierarchical_storage_context(tmp_path: Path) -> None:
    content = b"abc123"
    upload = SimpleNamespace(filename="../Trap Image 01.JPG", file=BytesIO(content))
    saved = save_upload_file(
        tmp_path,
        upload,
        field_id="field-1",
        trap_code="North Edge",
        capture_date=date(2026, 5, 4),
    )

    assert saved.exists()
    assert saved.read_bytes() == content
    assert saved.parent == tmp_path / "field-1" / "2026" / "05" / "04" / "North-Edge"
    assert saved.name.endswith("_TrapImage01.JPG")
    assert build_upload_storage_path(tmp_path, "field-1", "North Edge", date(2026, 5, 4)).samefile(saved.parent)


def test_upload_file_validation_rejects_unsupported_and_dataset_names() -> None:
    with pytest.raises(ValueError, match="Unsupported image type"):
        validate_upload_file(SimpleNamespace(filename="trap.gif", file=BytesIO(b"GIF89a")))

    with pytest.raises(ValueError, match="Training/validation/test dataset images"):
        validate_upload_file(SimpleNamespace(filename="training-sample.jpg", file=BytesIO(JPEG_BYTES)))


def test_upload_file_validation_checks_image_signature() -> None:
    validate_upload_file(SimpleNamespace(filename="trap.jpg", file=BytesIO(JPEG_BYTES)))
    validate_upload_file(SimpleNamespace(filename="trap.png", file=BytesIO(PNG_BYTES)))
    validate_upload_file(SimpleNamespace(filename="trap.webp", file=BytesIO(WEBP_BYTES)))

    spoofed = BytesIO(b"not-an-image")
    with pytest.raises(ValueError, match="content does not match"):
        validate_upload_file(SimpleNamespace(filename="trap.jpg", file=spoofed))
    assert spoofed.tell() == 0


def test_upload_metadata_normalization_and_format_validation() -> None:
    assert normalize_optional_text("  field-1  ") == "field-1"
    assert normalize_optional_text("   ") is None

    validate_identifier("field_1-A", "field_id")
    validate_trap_code("Trap 1-A")

    with pytest.raises(ValueError, match="field_id must contain only"):
        validate_identifier("field 1", "field_id")

    with pytest.raises(ValueError, match="trap_code must contain only"):
        validate_trap_code("Trap/1")
