from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import re
from typing import List, Sequence
from uuid import uuid4

from fastapi import UploadFile

ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
MAX_UPLOAD_SIZE_MB = 20
MAX_BATCH_UPLOAD_IMAGES = 50
_DATASET_FILENAME_MARKER = re.compile(r"(^|[^a-z])(train|training|valid|validation|test)([^a-z]|$)", re.IGNORECASE)
IDENTIFIER_PATTERN = re.compile(r'^[A-Za-z0-9_-]+$')
TRAP_CODE_PATTERN = re.compile(r'^[A-Za-z0-9 _-]+$')
STORAGE_SEGMENT_PATTERN = re.compile(r'[^A-Za-z0-9_-]+')


def secure_filename(name: str) -> str:
    safe = ''.join(ch for ch in name if ch.isalnum() or ch in ('.', '-', '_'))
    safe = safe.lstrip('.')
    return safe or 'image.jpg'


def secure_storage_segment(value: str | None, fallback: str = 'unassigned') -> str:
    normalized = (value or '').strip()
    normalized = re.sub(r'\s+', '-', normalized)
    safe = STORAGE_SEGMENT_PATTERN.sub('', normalized).strip('-_')
    return safe or fallback


def allocate_capture_dates(start_date: date, end_date: date, count: int) -> List[date]:
    if count <= 0:
        return []
    if count == 1:
        return [start_date]
    total_days = (end_date - start_date).days
    step = total_days / float(count - 1)
    values: List[date] = []
    for index in range(count):
        offset = round(index * step)
        values.append(start_date + timedelta(days=offset))
    return values


def resolve_batch_capture_dates(
    start_date: date,
    end_date: date,
    count: int,
    explicit_capture_dates: Sequence[date] | None = None,
) -> List[date]:
    if explicit_capture_dates is None:
        return allocate_capture_dates(start_date, end_date, count)

    capture_dates = list(explicit_capture_dates)
    if len(capture_dates) != count:
        raise ValueError('capture_dates must contain exactly one date for each uploaded image')
    if any(capture_date < start_date or capture_date > end_date for capture_date in capture_dates):
        raise ValueError('capture_dates must fall within the submitted start_date and end_date range')
    return capture_dates


def validate_upload_file(upload: UploadFile) -> None:
    filename = upload.filename or ''
    if not filename:
        raise ValueError('Upload file must have a filename')

    if _DATASET_FILENAME_MARKER.search(filename):
        raise ValueError('Training/validation/test dataset images are not allowed for production upload endpoints')

    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXTENSIONS:
        allowed = ', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))
        raise ValueError(f'Unsupported image type "{suffix}". Allowed: {allowed}')


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def validate_identifier(value: str, field_name: str) -> None:
    if len(value) > 64:
        raise ValueError(f'{field_name} must be 64 characters or fewer')
    if not IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f'{field_name} must contain only letters, numbers, underscores, or hyphens')


def validate_trap_code(value: str) -> None:
    if len(value) > 64:
        raise ValueError('trap_code must be 64 characters or fewer')
    if not TRAP_CODE_PATTERN.fullmatch(value):
        raise ValueError('trap_code must contain only letters, numbers, spaces, underscores, or hyphens')


def build_upload_storage_path(upload_root: Path, field_id: str, trap_code: str, capture_date: date) -> Path:
    return (
        upload_root
        / secure_storage_segment(field_id, 'field-unknown')
        / f'{capture_date:%Y}'
        / f'{capture_date:%m}'
        / f'{capture_date:%d}'
        / secure_storage_segment(trap_code, 'trap-unknown')
    )


def save_upload_file(
    upload_root: Path,
    upload: UploadFile,
    *,
    field_id: str | None = None,
    trap_code: str | None = None,
    capture_date: date | None = None,
) -> Path:
    destination_dir = (
        build_upload_storage_path(upload_root, field_id, trap_code, capture_date)
        if field_id and trap_code and capture_date
        else upload_root
    )
    destination_dir.mkdir(parents=True, exist_ok=True)
    filename = f'{uuid4().hex}_{secure_filename(upload.filename or "upload.jpg")}'
    destination = destination_dir / filename
    max_bytes = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    size_bytes = 0
    try:
        with destination.open('wb') as out_file:
            while True:
                chunk = upload.file.read(1024 * 1024)
                if not chunk:
                    break
                size_bytes += len(chunk)
                if size_bytes > max_bytes:
                    raise ValueError(f'Upload exceeds max size of {MAX_UPLOAD_SIZE_MB} MB')
                out_file.write(chunk)
        if size_bytes == 0:
            raise ValueError('Uploaded file is empty')
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return destination
