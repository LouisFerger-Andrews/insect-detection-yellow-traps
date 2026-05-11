#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from uuid import uuid4

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Detection, FieldMap, TrapPoint, TrapUpload, User
from app.services.graph_service import GraphService
from app.services.environment_service import infer_sync_end_date, infer_sync_start_date, sync_environment_for_field
from app.services.inference_service import InferenceService
from app.utils.geo import assign_grid_codes, polygon_area_m2

DEFAULT_FIELD_ID = 'field-brightlands-history-2025'
DEFAULT_FIELD_NAME = 'Brightlands History 2025'
DEFAULT_OUTPUT_SUBDIR = 'brightlands_history_2025_import'

# Approximate Brightlands Campus Greenport (Venlo) bounding polygon.
POLYGON = [
    {'lat': 51.36282, 'lng': 6.16746},
    {'lat': 51.36282, 'lng': 6.16908},
    {'lat': 51.36178, 'lng': 6.16908},
    {'lat': 51.36178, 'lng': 6.16746},
]


@dataclass
class SourceImage:
    capture_date: date
    path: Path


def parse_capture_date_from_dir(dirname: str) -> date | None:
    parts = dirname.split('-')
    if len(parts) != 3:
        return None
    try:
        day = int(parts[0])
        month = int(parts[1])
        year = int(parts[2])
        return date(year, month, day)
    except ValueError:
        return None


def iter_source_images(root: Path) -> list[SourceImage]:
    valid_ext = {'.heic', '.heif', '.jpg', '.jpeg', '.png', '.jfif'}
    rows: list[SourceImage] = []
    for path in root.rglob('*'):
        if not path.is_file():
            continue
        if path.suffix.lower() not in valid_ext:
            continue
        capture_date = parse_capture_date_from_dir(path.parent.name)
        if capture_date is None:
            continue
        rows.append(SourceImage(capture_date=capture_date, path=path))
    rows.sort(key=lambda item: (item.capture_date, item.path.name))
    return rows


def convert_to_jpg(source_path: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = source_path.suffix.lower()

    if suffix in {'.heic', '.heif', '.png', '.jfif'}:
        # macOS-native converter handles HEIC/JFIF reliably.
        subprocess.run(
            ['sips', '-s', 'format', 'jpeg', str(source_path), '--out', str(output_path)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return

    if suffix in {'.jpg', '.jpeg'}:
        if source_path.resolve() != output_path.resolve():
            shutil.copy2(source_path, output_path)
        return

    raise ValueError(f'Unsupported image format: {source_path}')


def build_trap_grid() -> list[tuple[float, float]]:
    # 4 rows x 5 positions inside polygon bounds.
    top = max(point['lat'] for point in POLYGON) - 0.00010
    bottom = min(point['lat'] for point in POLYGON) + 0.00010
    left = min(point['lng'] for point in POLYGON) + 0.00012
    right = max(point['lng'] for point in POLYGON) - 0.00012

    rows = 4
    cols = 5
    lat_step = (top - bottom) / max(rows - 1, 1)
    lng_step = (right - left) / max(cols - 1, 1)

    coords: list[tuple[float, float]] = []
    for r_idx in range(rows):
        lat = top - r_idx * lat_step
        for c_idx in range(cols):
            lng = left + c_idx * lng_step
            coords.append((lat, lng))
    return coords


def ensure_field_and_traps(db: Session, owner_user: User, field_id: str, field_name: str) -> list[TrapPoint]:
    field = db.query(FieldMap).filter(FieldMap.id == field_id).first()
    if field is None:
        area_m2 = polygon_area_m2([(point['lat'], point['lng']) for point in POLYGON])
        field = FieldMap(
            id=field_id,
            owner_user_id=owner_user.id,
            name=field_name,
            polygon_geojson=json.dumps(POLYGON),
            area_m2=area_m2,
        )
        db.add(field)
        db.flush()

    traps = db.query(TrapPoint).filter(TrapPoint.field_id == field_id).order_by(TrapPoint.row_index, TrapPoint.position_index).all()
    if len(traps) == 20:
        return traps

    existing_upload_count = db.query(TrapUpload).filter(TrapUpload.field_id == field_id).count()
    if existing_upload_count > 0 and len(traps) != 20:
        raise RuntimeError('Field exists with uploads but trap count is not 20; refusing destructive trap reset.')

    for trap in traps:
        db.delete(trap)
    db.flush()

    traps = []
    for lat, lng in build_trap_grid():
        traps.append(
            TrapPoint(
                id=f'trap-{uuid4().hex[:16]}',
                field_id=field_id,
                code='PENDING',
                custom_name=None,
                latitude=lat,
                longitude=lng,
                row_index=0,
                position_index=0,
            )
        )
    db.add_all(traps)
    db.flush()

    assignments = assign_grid_codes([(trap.id, trap.latitude, trap.longitude) for trap in traps], row_tolerance_m=10.0)
    by_id = {trap.id: trap for trap in traps}
    for trap_id, row_index, position_index, code in assignments:
        trap = by_id[trap_id]
        trap.row_index = row_index
        trap.position_index = position_index
        trap.code = code
        trap.custom_name = f'{code}'

    db.commit()
    return db.query(TrapPoint).filter(TrapPoint.field_id == field_id).order_by(TrapPoint.row_index, TrapPoint.position_index).all()


def _safe_name(value: str) -> str:
    return ''.join(char if char.isalnum() or char in {'-', '_'} else '-' for char in value)


def import_dataset(
    source_root: Path,
    field_id: str,
    field_name: str,
    output_subdir: str,
    limit: int | None = None,
    seed: int = 2025,
) -> None:
    settings = get_settings()
    uploads_root = Path(settings.upload_dir).resolve()
    infer = InferenceService()
    graph = GraphService()
    rng = random.Random(seed)

    rows = iter_source_images(source_root)
    if limit is not None:
        rows = rows[:limit]
    if not rows:
        raise RuntimeError(f'No importable images found in {source_root}')

    with SessionLocal() as db:
        owner_user = db.query(User).filter(User.email == settings.admin_email.lower()).first()
        if owner_user is None:
            raise RuntimeError(f'Admin user not found: {settings.admin_email.lower()}')

        traps = ensure_field_and_traps(db, owner_user, field_id=field_id, field_name=field_name)
        graph.initialize()
        graph.ensure_user_node(owner_user.id, owner_user.email, owner_user.full_name)

        created = 0
        skipped = 0
        failed = 0
        for idx, row in enumerate(rows):
            trap = traps[idx % len(traps)]
            side = rng.choice(['A', 'B'])
            day_folder = row.capture_date.isoformat()
            output_dir = uploads_root / output_subdir / day_folder
            output_filename = f'{day_folder}_{_safe_name(row.path.stem)}.jpg'
            output_path = output_dir / output_filename

            existing_upload = (
                db.query(TrapUpload)
                .filter(
                    TrapUpload.field_id == field_id,
                    TrapUpload.image_path == str(output_path),
                    TrapUpload.capture_date == row.capture_date,
                )
                .first()
            )
            if existing_upload is not None:
                skipped += 1
                continue

            try:
                convert_to_jpg(row.path, output_path)
                detections = infer.run(output_path)
                confidence_avg = sum(item['confidence'] for item in detections) / len(detections) if detections else 0.0

                trap_code = f'{trap.custom_name or trap.code}-S{side}'
                upload = TrapUpload(
                    user_id=owner_user.id,
                    field_id=field_id,
                    trap_id=trap.id,
                    trap_code=trap_code,
                    capture_date=row.capture_date,
                    image_path=str(output_path),
                    detection_count=len(detections),
                    confidence_avg=float(confidence_avg),
                )
                db.add(upload)
                db.flush()

                for item in detections:
                    bbox = item['bbox_xyxy']
                    db.add(
                        Detection(
                            upload_id=upload.id,
                            class_id=int(item['class_id']),
                            confidence=float(item['confidence']),
                            x1=float(bbox[0]),
                            y1=float(bbox[1]),
                            x2=float(bbox[2]),
                            y2=float(bbox[3]),
                        )
                    )

                db.commit()
                graph.link_upload_to_field(field_id, upload.id, upload.capture_date, upload.detection_count)
                created += 1
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                failed += 1
                print(f'FAILED: {row.path} ({exc})')

        # Ensure all upload dates for this field have environmental data.
        sync_start = infer_sync_start_date(db, field_id)
        sync_end = infer_sync_end_date(db, field_id)
        if sync_start is not None and sync_end is not None:
            field = db.query(FieldMap).filter(FieldMap.id == field_id).first()
            if field is not None:
                sync_environment_for_field(db, field, sync_start, sync_end)

    graph.close()
    print(
        json.dumps(
            {
                'field_id': field_id,
                'field_name': field_name,
                'source_root': str(source_root),
                'created_uploads': created,
                'skipped_existing': skipped,
                'failed': failed,
            },
            indent=2,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Import Brightlands trap images into SWD backend')
    parser.add_argument(
        '--source',
        type=Path,
        default=Path('/Users/louis.ferger-andrews/Desktop/2025'),
        help='Root directory with dated folders (default: /Users/louis.ferger-andrews/Desktop/2025).',
    )
    parser.add_argument('--field-id', type=str, default=DEFAULT_FIELD_ID, help='Target FieldMap.id to import into.')
    parser.add_argument('--field-name', type=str, default=DEFAULT_FIELD_NAME, help='Target FieldMap.name to import into.')
    parser.add_argument(
        '--output-subdir',
        type=str,
        default=DEFAULT_OUTPUT_SUBDIR,
        help='Upload storage subdirectory name under backend UPLOAD_DIR.',
    )
    parser.add_argument('--limit', type=int, default=None, help='Optional max number of images to import')
    parser.add_argument('--seed', type=int, default=2025, help='Random seed for side A/B assignment')
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = args.source.expanduser().resolve()
    if not source.exists():
        raise SystemExit(f'Source directory does not exist: {source}')
    import_dataset(
        source_root=source,
        field_id=args.field_id,
        field_name=args.field_name,
        output_subdir=args.output_subdir,
        limit=args.limit,
        seed=args.seed,
    )


if __name__ == '__main__':
    main()
