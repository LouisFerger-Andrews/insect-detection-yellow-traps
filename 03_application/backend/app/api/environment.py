from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, extract, func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import EnvironmentalDaily, EnvironmentalSourceDaily, FieldMap, TrapUpload, User
from app.services.environment_service import infer_sync_end_date, infer_sync_start_date, sync_environment_for_field
from app.services.upload_visibility import apply_production_upload_filter

router = APIRouter(prefix='/api/environment', tags=['environment'])


def _get_field_or_403(db: Session, field_id: str, current_user: User) -> FieldMap:
    field = db.query(FieldMap).filter(FieldMap.id == field_id).first()
    if field is None:
        raise HTTPException(status_code=404, detail='Field not found')
    if current_user.role != 'admin' and field.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail='Forbidden')
    return field


@router.post('/fields/{field_id}/sync')
def sync_field_environment(
    field_id: str,
    body: dict | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    field = _get_field_or_403(db, field_id, current_user)
    payload = body or {}

    force_start = payload.get('start_date')
    force_end = payload.get('end_date')

    start_date = date.fromisoformat(force_start) if force_start else infer_sync_start_date(db, field.id)
    if start_date is None:
        raise HTTPException(
            status_code=400,
            detail='No trap uploads found yet for this field. Upload at least one trap image first.',
        )
    end_date = date.fromisoformat(force_end) if force_end else (infer_sync_end_date(db, field.id) or date.today())

    result = sync_environment_for_field(db, field, start_date, end_date)
    return {
        'field_id': field.id,
        'field_name': field.name,
        **result,
    }


@router.get('/overview')
def environment_overview(
    year: int | None = Query(default=None, ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    field_query = db.query(FieldMap)
    if current_user.role != 'admin':
        field_query = field_query.filter(FieldMap.owner_user_id == current_user.id)
    fields = field_query.order_by(FieldMap.created_at.desc()).all()

    years_query = db.query(extract('year', EnvironmentalDaily.observation_date).label('year')).distinct()
    if current_user.role != 'admin':
        years_query = years_query.join(FieldMap, FieldMap.id == EnvironmentalDaily.field_id).filter(FieldMap.owner_user_id == current_user.id)
    available_years = [int(row.year) for row in years_query.order_by('year').all() if row.year is not None]

    output = []
    for field in fields:
        row_query = db.query(
            func.count(EnvironmentalDaily.id).label('records'),
            func.min(EnvironmentalDaily.observation_date).label('start_date'),
            func.max(EnvironmentalDaily.observation_date).label('end_date'),
            func.max(EnvironmentalDaily.fetched_at).label('last_fetch_at'),
        ).filter(EnvironmentalDaily.field_id == field.id)
        latest_query = db.query(EnvironmentalDaily).filter(EnvironmentalDaily.field_id == field.id)
        if year is not None:
            row_query = row_query.filter(extract('year', EnvironmentalDaily.observation_date) == year)
            latest_query = latest_query.filter(extract('year', EnvironmentalDaily.observation_date) == year)
        row = row_query.one()
        latest = latest_query.order_by(EnvironmentalDaily.observation_date.desc()).first()
        source_query = db.query(
            EnvironmentalSourceDaily.provider.label('provider'),
            func.count(EnvironmentalSourceDaily.id).label('count'),
        ).filter(EnvironmentalSourceDaily.field_id == field.id)
        if year is not None:
            source_query = source_query.filter(extract('year', EnvironmentalSourceDaily.observation_date) == year)
        output.append(
            {
                'field_id': field.id,
                'field_name': field.name,
                'records': int(row.records or 0),
                'start_date': str(row.start_date) if row.start_date else None,
                'end_date': str(row.end_date) if row.end_date else None,
                'last_fetch_at': row.last_fetch_at.isoformat() if row.last_fetch_at else None,
                'latest': (
                    {
                        'date': str(latest.observation_date),
                        'temperature_mean_c': latest.temperature_mean_c,
                        'precipitation_mm': latest.precipitation_mm,
                        'gdd_base10_c': latest.gdd_base10_c,
                        'water_deficit_mm': latest.water_deficit_mm,
                    }
                    if latest
                    else None
                ),
                'sources': {
                    provider: int(count)
                    for provider, count in source_query.group_by(EnvironmentalSourceDaily.provider).all()
                },
            }
        )

    return {'selected_year': year, 'available_years': available_years, 'fields': output}


@router.get('/fields/{field_id}/timeseries')
def environment_field_timeseries(
    field_id: str,
    weeks: int = Query(default=10, ge=1, le=520),
    all_data: bool = False,
    year: int | None = Query(default=None, ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    field = _get_field_or_403(db, field_id, current_user)

    # derive range from most recent upload/environment date
    upload_query = apply_production_upload_filter(db.query(TrapUpload)).filter(TrapUpload.field_id == field.id)
    env_query = db.query(EnvironmentalDaily).filter(EnvironmentalDaily.field_id == field.id)
    if year is not None:
        upload_query = upload_query.filter(extract('year', TrapUpload.capture_date) == year)
        env_query = env_query.filter(extract('year', EnvironmentalDaily.observation_date) == year)

    latest_upload_date = upload_query.with_entities(func.max(TrapUpload.capture_date)).scalar()
    earliest_upload_date = upload_query.with_entities(func.min(TrapUpload.capture_date)).scalar()
    latest_env_date = env_query.with_entities(func.max(EnvironmentalDaily.observation_date)).scalar()
    earliest_env_date = env_query.with_entities(func.min(EnvironmentalDaily.observation_date)).scalar()

    latest_candidates = [d for d in [latest_upload_date, latest_env_date] if d is not None]
    latest_date = max(latest_candidates) if latest_candidates else date.today()

    if all_data:
        earliest_candidates = [d for d in [earliest_upload_date, earliest_env_date] if d is not None]
        start_date = min(earliest_candidates) if earliest_candidates else latest_date
        window_weeks = max(1, ((latest_date - start_date).days // 7) + 1)
    else:
        start_date = latest_date - timedelta(days=weeks * 7 - 1)
        window_weeks = weeks

    pop_rows = (
        apply_production_upload_filter(
            db.query(
            func.date_trunc('week', TrapUpload.capture_date).label('week_start'),
            func.count(TrapUpload.id).label('uploads'),
            func.coalesce(func.avg(TrapUpload.detection_count), 0.0).label('avg_population'),
            func.coalesce(func.sum(TrapUpload.detection_count), 0).label('total_population'),
        )
        )
        .filter(
            and_(
                TrapUpload.field_id == field.id,
                TrapUpload.capture_date >= start_date,
                TrapUpload.capture_date <= latest_date,
            )
        )
        .filter(extract('year', TrapUpload.capture_date) == year if year is not None else True)
        .group_by(func.date_trunc('week', TrapUpload.capture_date))
        .order_by(func.date_trunc('week', TrapUpload.capture_date))
        .all()
    )

    trap_weekly_rows = (
        apply_production_upload_filter(
            db.query(
            func.date_trunc('week', TrapUpload.capture_date).label('week_start'),
            TrapUpload.trap_code.label('trap_code'),
            func.count(TrapUpload.id).label('uploads'),
            func.coalesce(func.avg(TrapUpload.detection_count), 0.0).label('avg_population'),
            func.coalesce(func.sum(TrapUpload.detection_count), 0).label('total_population'),
        )
        )
        .filter(
            and_(
                TrapUpload.field_id == field.id,
                TrapUpload.capture_date >= start_date,
                TrapUpload.capture_date <= latest_date,
            )
        )
        .filter(extract('year', TrapUpload.capture_date) == year if year is not None else True)
        .group_by(func.date_trunc('week', TrapUpload.capture_date), TrapUpload.trap_code)
        .order_by(func.date_trunc('week', TrapUpload.capture_date), TrapUpload.trap_code)
        .all()
    )

    weather_rows = (
        db.query(
            func.date_trunc('week', EnvironmentalDaily.observation_date).label('week_start'),
            func.coalesce(func.avg(EnvironmentalDaily.temperature_mean_c), 0.0).label('temp_avg'),
            func.coalesce(func.sum(EnvironmentalDaily.precipitation_mm), 0.0).label('rain_sum'),
            func.coalesce(func.avg(EnvironmentalDaily.gdd_base10_c), 0.0).label('gdd_avg'),
            func.coalesce(func.avg(EnvironmentalDaily.water_deficit_mm), 0.0).label('deficit_avg'),
            func.coalesce(func.avg(EnvironmentalDaily.heat_stress_c), 0.0).label('heat_stress_avg'),
        )
        .filter(
            and_(
                EnvironmentalDaily.field_id == field.id,
                EnvironmentalDaily.observation_date >= start_date,
                EnvironmentalDaily.observation_date <= latest_date,
            )
        )
        .filter(extract('year', EnvironmentalDaily.observation_date) == year if year is not None else True)
        .group_by(func.date_trunc('week', EnvironmentalDaily.observation_date))
        .order_by(func.date_trunc('week', EnvironmentalDaily.observation_date))
        .all()
    )

    pop_weekly = [
        {
            'week_start': row.week_start.date().isoformat() if hasattr(row.week_start, 'date') else str(row.week_start)[:10],
            'uploads': int(row.uploads or 0),
            'avg_population': round(float(row.avg_population or 0.0), 3),
            'total_population': int(row.total_population or 0),
        }
        for row in pop_rows
    ]
    weather_weekly = [
        {
            'week_start': row.week_start.date().isoformat() if hasattr(row.week_start, 'date') else str(row.week_start)[:10],
            'temp_avg': round(float(row.temp_avg or 0.0), 3),
            'rain_sum': round(float(row.rain_sum or 0.0), 3),
            'gdd_avg': round(float(row.gdd_avg or 0.0), 3),
            'deficit_avg': round(float(row.deficit_avg or 0.0), 3),
            'heat_stress_avg': round(float(row.heat_stress_avg or 0.0), 3),
        }
        for row in weather_rows
    ]
    trap_weekly = [
        {
            'week_start': row.week_start.date().isoformat() if hasattr(row.week_start, 'date') else str(row.week_start)[:10],
            'trap_code': row.trap_code,
            'uploads': int(row.uploads or 0),
            'avg_population': round(float(row.avg_population or 0.0), 3),
            'total_population': int(row.total_population or 0),
        }
        for row in trap_weekly_rows
    ]

    return {
        'field_id': field.id,
        'field_name': field.name,
        'weeks': window_weeks,
        'selected_year': year,
        'all_data': all_data,
        'start_date': start_date.isoformat(),
        'end_date': latest_date.isoformat(),
        'population_weekly': pop_weekly,
        'weather_weekly': weather_weekly,
        'trap_weekly': trap_weekly,
    }
