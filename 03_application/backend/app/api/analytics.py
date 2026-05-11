from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import FieldMap, TrapUpload, User
from app.services.upload_visibility import apply_production_upload_filter

router = APIRouter(prefix='/api/analytics', tags=['analytics'])


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
        field = db.query(FieldMap).filter(FieldMap.id == field_id).first()
        if field is None:
            raise HTTPException(status_code=404, detail='Field not found')
        if current_user.role != 'admin' and field.owner_user_id != current_user.id:
            raise HTTPException(status_code=403, detail='Forbidden')
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
