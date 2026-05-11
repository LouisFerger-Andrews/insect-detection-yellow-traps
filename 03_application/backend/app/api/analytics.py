from datetime import date
import csv
from io import StringIO
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.api.access import require_field_access
from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models import Detection, FieldMap, TrapUpload, User
from app.services.upload_visibility import apply_production_upload_filter

router = APIRouter(prefix='/api/analytics', tags=['analytics'])


def _apply_insight_filters(
    query,
    *,
    current_user: User,
    field_id: str | None,
    trap_id: str | None = None,
    trap_code: str | None,
    start_date: date | None,
    end_date: date | None,
    min_detections: int | None,
    max_detections: int | None,
    min_confidence: float | None,
):
    if current_user.role != 'admin':
        query = query.filter(FieldMap.owner_user_id == current_user.id)
    if field_id is not None:
        query = query.filter(TrapUpload.field_id == field_id)
    if trap_id is not None:
        query = query.filter(TrapUpload.trap_id == trap_id)
    if trap_code is not None:
        query = query.filter(TrapUpload.trap_code == trap_code)
    if start_date is not None:
        query = query.filter(TrapUpload.capture_date >= start_date)
    if end_date is not None:
        query = query.filter(TrapUpload.capture_date <= end_date)
    if min_detections is not None:
        query = query.filter(TrapUpload.detection_count >= min_detections)
    if max_detections is not None:
        query = query.filter(TrapUpload.detection_count <= max_detections)
    if min_confidence is not None:
        query = query.filter(TrapUpload.confidence_avg >= min_confidence)
    return query


def _validate_field_access(db: Session, field_id: str | None, current_user: User) -> None:
    if field_id is None:
        return
    require_field_access(db, field_id, current_user)


def _insight_payload(
    *,
    db: Session,
    current_user: User,
    field_id: str | None,
    trap_id: str | None = None,
    trap_code: str | None,
    start_date: date | None,
    end_date: date | None,
    min_detections: int | None,
    max_detections: int | None,
    min_confidence: float | None,
):
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(status_code=400, detail='start_date must be before or equal to end_date')
    if min_detections is not None and max_detections is not None and min_detections > max_detections:
        raise HTTPException(status_code=400, detail='min_detections must be less than or equal to max_detections')
    _validate_field_access(db, field_id, current_user)

    base_query = apply_production_upload_filter(
        db.query(TrapUpload, FieldMap).join(FieldMap, FieldMap.id == TrapUpload.field_id)
    )
    rows = (
        _apply_insight_filters(
            base_query,
            current_user=current_user,
            field_id=field_id,
            trap_id=trap_id,
            trap_code=trap_code,
            start_date=start_date,
            end_date=end_date,
            min_detections=min_detections,
            max_detections=max_detections,
            min_confidence=min_confidence,
        )
        .order_by(TrapUpload.capture_date.desc(), TrapUpload.id.desc())
        .limit(500)
        .all()
    )

    upload_ids = [upload.id for upload, _field in rows]
    detection_rows = (
        db.query(Detection).filter(Detection.upload_id.in_(upload_ids)).order_by(Detection.upload_id.asc(), Detection.id.asc()).all()
        if upload_ids
        else []
    )
    detections_by_upload: dict[int, list[Detection]] = {}
    for detection in detection_rows:
        detections_by_upload.setdefault(detection.upload_id, []).append(detection)

    total_images = len(rows)
    total_detections = sum(upload.detection_count for upload, _field in rows)
    avg_detections = total_detections / total_images if total_images else 0.0

    field_totals: dict[str, dict] = {}
    trap_totals: dict[str, dict] = {}
    trend_totals: dict[str, dict] = {}
    for upload, field in rows:
        field_bucket = field_totals.setdefault(
            field.id,
            {'field_id': field.id, 'field_name': field.name, 'images': 0, 'detections': 0},
        )
        field_bucket['images'] += 1
        field_bucket['detections'] += upload.detection_count

        trap_bucket = trap_totals.setdefault(
            upload.trap_code,
            {'trap_code': upload.trap_code, 'images': 0, 'detections': 0},
        )
        trap_bucket['images'] += 1
        trap_bucket['detections'] += upload.detection_count

        date_key = upload.capture_date.isoformat()
        trend_bucket = trend_totals.setdefault(date_key, {'capture_date': date_key, 'images': 0, 'detections': 0})
        trend_bucket['images'] += 1
        trend_bucket['detections'] += upload.detection_count

    by_field = sorted(field_totals.values(), key=lambda item: item['detections'], reverse=True)
    by_trap = sorted(trap_totals.values(), key=lambda item: item['detections'], reverse=True)
    trend = sorted(trend_totals.values(), key=lambda item: item['capture_date'])
    for row in [*by_field, *by_trap, *trend]:
        row['avg_detections_per_image'] = round(row['detections'] / row['images'], 3) if row['images'] else 0.0

    settings = get_settings()
    return {
        'context': {
            'scope': 'all-fields' if current_user.role == 'admin' else 'owned-fields',
            'dataset_version': 'metadata-v1.0.0',
            'model_version': Path(settings.model_weights_path).name,
            'filters': {
                'field_id': field_id,
                'trap_id': trap_id,
                'trap_code': trap_code,
                'start_date': start_date.isoformat() if start_date else None,
                'end_date': end_date.isoformat() if end_date else None,
                'min_detections': min_detections,
                'max_detections': max_detections,
                'min_confidence': min_confidence,
            },
        },
        'kpis': {
            'processed_images': total_images,
            'total_detections': total_detections,
            'avg_detections_per_image': round(avg_detections, 3),
            'highest_activity_field': by_field[0] if by_field else None,
            'highest_activity_trap': by_trap[0] if by_trap else None,
        },
        'trend': trend,
        'comparisons': {
            'by_field': by_field,
            'by_trap': by_trap,
        },
        'results': [
            {
                'upload_id': upload.id,
                'image_path': upload.image_path,
                'field_id': field.id,
                'field_name': field.name,
                'trap_id': upload.trap_id,
                'trap_code': upload.trap_code,
                'capture_date': upload.capture_date.isoformat(),
                'detection_count': upload.detection_count,
                'confidence_avg': round(float(upload.confidence_avg), 4),
                'detections': [
                    {
                        'class_id': detection.class_id,
                        'confidence': detection.confidence,
                        'bbox_xyxy': [detection.x1, detection.y1, detection.x2, detection.y2],
                    }
                    for detection in detections_by_upload.get(upload.id, [])
                ],
            }
            for upload, field in rows
        ],
    }


@router.get('/insights')
def insight_dashboard(
    field_id: str | None = Query(default=None),
    trap_id: str | None = None,
    trap_code: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    min_detections: int | None = Query(default=None, ge=0),
    max_detections: int | None = Query(default=None, ge=0),
    min_confidence: float | None = Query(default=None, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _insight_payload(
        db=db,
        current_user=current_user,
        field_id=field_id,
        trap_id=trap_id,
        trap_code=trap_code,
        start_date=start_date,
        end_date=end_date,
        min_detections=min_detections,
        max_detections=max_detections,
        min_confidence=min_confidence,
    )


@router.get('/insights/export.csv')
def export_insight_dashboard_csv(
    field_id: str | None = Query(default=None),
    trap_id: str | None = None,
    trap_code: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    min_detections: int | None = Query(default=None, ge=0),
    max_detections: int | None = Query(default=None, ge=0),
    min_confidence: float | None = Query(default=None, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payload = _insight_payload(
        db=db,
        current_user=current_user,
        field_id=field_id,
        trap_id=trap_id,
        trap_code=trap_code,
        start_date=start_date,
        end_date=end_date,
        min_detections=min_detections,
        max_detections=max_detections,
        min_confidence=min_confidence,
    )
    output = StringIO()
    writer = csv.writer(output)
    context = payload['context']
    writer.writerow(['report', 'Insight dashboard export'])
    writer.writerow(['dataset_version', context['dataset_version']])
    writer.writerow(['model_version', context['model_version']])
    writer.writerow(['scope', context['scope']])
    for key, value in context['filters'].items():
        writer.writerow([f'filter_{key}', '' if value is None else value])
    writer.writerow([])
    writer.writerow([
        'upload_id',
        'image_path',
        'field_id',
        'field_name',
        'trap_id',
        'trap_code',
        'capture_date',
        'detection_count',
        'confidence_avg',
        'prediction_count',
        'prediction_metadata',
    ])
    for result in payload['results']:
        writer.writerow([
            result['upload_id'],
            result['image_path'],
            result['field_id'],
            result['field_name'],
            result['trap_id'] or '',
            result['trap_code'],
            result['capture_date'],
            result['detection_count'],
            result['confidence_avg'],
            len(result['detections']),
            '; '.join(
                f"class={item['class_id']} conf={item['confidence']:.4f} bbox={item['bbox_xyxy']}"
                for item in result['detections']
            ),
        ])
    return Response(
        content=output.getvalue(),
        media_type='text/csv',
        headers={'Content-Disposition': 'attachment; filename="insight-dashboard-export.csv"'},
    )


@router.get('/overview')
def analytics_overview(
    field_id: str | None = Query(default=None),
    year: int | None = Query(default=None, ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    years_query = apply_production_upload_filter(
        db.query(extract('year', TrapUpload.capture_date)).join(FieldMap, FieldMap.id == TrapUpload.field_id)
    )
    if current_user.role != 'admin':
        years_query = years_query.filter(FieldMap.owner_user_id == current_user.id)
    if field_id is not None:
        require_field_access(db, field_id, current_user)
        years_query = years_query.filter(TrapUpload.field_id == field_id)
    available_year_rows = years_query.distinct().order_by(extract('year', TrapUpload.capture_date)).all()
    available_years = [int(row[0]) for row in available_year_rows if row[0] is not None]

    query = apply_production_upload_filter(db.query(TrapUpload, FieldMap).join(FieldMap, FieldMap.id == TrapUpload.field_id))
    if current_user.role != 'admin':
        query = query.filter(FieldMap.owner_user_id == current_user.id)
    if field_id is not None:
        query = query.filter(TrapUpload.field_id == field_id)
    if year is not None:
        query = query.filter(extract('year', TrapUpload.capture_date) == year)

    rows = query.all()
    upload_ids = [row[0].id for row in rows]
    total_uploads = len(upload_ids)
    total_detections = sum(row[0].detection_count for row in rows)
    avg_detection = (total_detections / total_uploads) if total_uploads > 0 else 0.0

    daily_query = apply_production_upload_filter(
        db.query(
        TrapUpload.capture_date.label('capture_date'),
        func.count(TrapUpload.id).label('uploads'),
        func.sum(TrapUpload.detection_count).label('detections'),
    ).join(FieldMap, FieldMap.id == TrapUpload.field_id)
    )
    if current_user.role != 'admin':
        daily_query = daily_query.filter(FieldMap.owner_user_id == current_user.id)
    if field_id is not None:
        daily_query = daily_query.filter(TrapUpload.field_id == field_id)
    if year is not None:
        daily_query = daily_query.filter(extract('year', TrapUpload.capture_date) == year)
    daily_rows = (
        daily_query.group_by(TrapUpload.capture_date)
        .order_by(TrapUpload.capture_date.desc())
        .limit(30)
        .all()
    )

    field_query = apply_production_upload_filter(
        db.query(
        FieldMap.id.label('field_id'),
        FieldMap.name.label('field_name'),
        func.count(TrapUpload.id).label('uploads'),
        func.sum(TrapUpload.detection_count).label('detections'),
    ).join(TrapUpload, TrapUpload.field_id == FieldMap.id)
    )
    if current_user.role != 'admin':
        field_query = field_query.filter(FieldMap.owner_user_id == current_user.id)
    if field_id is not None:
        field_query = field_query.filter(FieldMap.id == field_id)
    if year is not None:
        field_query = field_query.filter(extract('year', TrapUpload.capture_date) == year)
    field_rows = (
        field_query.group_by(FieldMap.id, FieldMap.name)
        .order_by(func.sum(TrapUpload.detection_count).desc())
        .limit(20)
        .all()
    )

    trap_query = apply_production_upload_filter(
        db.query(
        TrapUpload.trap_code.label('trap_code'),
        func.count(TrapUpload.id).label('uploads'),
        func.sum(TrapUpload.detection_count).label('detections'),
    ).join(FieldMap, FieldMap.id == TrapUpload.field_id)
    )
    if current_user.role != 'admin':
        trap_query = trap_query.filter(FieldMap.owner_user_id == current_user.id)
    if field_id is not None:
        trap_query = trap_query.filter(TrapUpload.field_id == field_id)
    if year is not None:
        trap_query = trap_query.filter(extract('year', TrapUpload.capture_date) == year)
    trap_rows = (
        trap_query.group_by(TrapUpload.trap_code)
        .order_by(func.sum(TrapUpload.detection_count).desc())
        .limit(20)
        .all()
    )

    return {
        'scope': 'all-fields' if current_user.role == 'admin' else 'owned-fields',
        'selected_field_id': field_id,
        'selected_year': year,
        'available_years': available_years,
        'totals': {
            'uploads': total_uploads,
            'detections': total_detections,
            'avg_detection_per_upload': round(avg_detection, 3),
        },
        'daily': [
            {
                'capture_date': str(row.capture_date),
                'uploads': int(row.uploads or 0),
                'detections': int(row.detections or 0),
            }
            for row in daily_rows
        ],
        'by_field': [
            {
                'field_id': row.field_id,
                'field_name': row.field_name,
                'uploads': int(row.uploads or 0),
                'detections': int(row.detections or 0),
            }
            for row in field_rows
        ],
        'by_trap': [
            {
                'trap_code': row.trap_code,
                'uploads': int(row.uploads or 0),
                'detections': int(row.detections or 0),
            }
            for row in trap_rows
        ],
    }
