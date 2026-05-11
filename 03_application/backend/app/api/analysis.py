import json
from collections import defaultdict
from datetime import date
from html import escape
from pathlib import Path
import re
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import and_, extract, func
from sqlalchemy.orm import Session
import requests

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models import Detection, FieldMap, TrapPoint, TrapUpload, User
from app.schemas.upload import DetectionResponse, UploadBatchResponse, UploadResult, UploadSummary
from app.services.graph_service import GraphService
from app.services.environment_service import infer_sync_start_date, sync_environment_for_field
from app.services.inference_service import InferenceService
from app.services.upload_service import allocate_capture_dates, save_upload_file, validate_upload_file
from app.services.upload_visibility import apply_production_upload_filter

router = APIRouter(prefix='/api/analysis', tags=['analysis'])
logger = logging.getLogger(__name__)


@router.post('/upload-range', response_model=UploadBatchResponse)
def upload_range(
    start_date: date = Form(...),
    end_date: date = Form(...),
    field_id: str | None = Form(default=None),
    trap_id: str | None = Form(default=None),
    trap_code: str | None = Form(default=None),
    images: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if start_date > end_date:
        raise HTTPException(status_code=400, detail='start_date must be before or equal to end_date')
    if not images:
        raise HTTPException(status_code=400, detail='At least one image is required')

    capture_dates = allocate_capture_dates(start_date, end_date, len(images))
    settings = get_settings()
    upload_root = Path(settings.upload_dir)
    infer = InferenceService()

    if trap_id:
        trap = db.query(TrapPoint).filter(TrapPoint.id == trap_id).first()
        if trap is None:
            raise HTTPException(status_code=404, detail='Trap not found')
        field = db.query(FieldMap).filter(FieldMap.id == trap.field_id).first()
        if field is None:
            raise HTTPException(status_code=404, detail='Field not found')
        if current_user.role != 'admin' and field.owner_user_id != current_user.id:
            raise HTTPException(status_code=403, detail='Forbidden')
        resolved_field_id = field.id
        resolved_trap_code = trap.custom_name or trap.code
    else:
        if not field_id:
            raise HTTPException(status_code=400, detail='field_id is required when trap_id is not provided')
        field = db.query(FieldMap).filter(FieldMap.id == field_id).first()
        if field is None:
            raise HTTPException(status_code=404, detail='Field not found')
        if current_user.role != 'admin' and field.owner_user_id != current_user.id:
            raise HTTPException(status_code=403, detail='Forbidden')
        resolved_field_id = field.id
        resolved_trap_code = trap_code or 'UNSPECIFIED'

    for file in images:
        try:
            validate_upload_file(file)
        except ValueError as exc:
            logger.warning('Upload validation failed for user=%s file=%s: %s', current_user.id, file.filename, exc)
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    graph = GraphService()

    results: list[UploadResult] = []
    try:
        for idx, file in enumerate(images):
            try:
                saved_path = save_upload_file(upload_root, file)
                detections = infer.run(saved_path)
            except ValueError as exc:
                logger.warning('Upload validation failed for user=%s file=%s: %s', current_user.id, file.filename, exc)
                raise HTTPException(status_code=400, detail=str(exc)) from exc

            confidence_avg = sum(d['confidence'] for d in detections) / len(detections) if detections else 0.0

            upload = TrapUpload(
                user_id=current_user.id,
                field_id=resolved_field_id,
                trap_id=trap_id,
                trap_code=resolved_trap_code,
                capture_date=capture_dates[idx],
                image_path=str(saved_path),
                detection_count=len(detections),
                confidence_avg=float(confidence_avg),
            )
            db.add(upload)
            db.flush()

            for detection in detections:
                bbox = detection['bbox_xyxy']
                db.add(
                    Detection(
                        upload_id=upload.id,
                        class_id=detection['class_id'],
                        confidence=detection['confidence'],
                        x1=bbox[0],
                        y1=bbox[1],
                        x2=bbox[2],
                        y2=bbox[3],
                    )
                )

            db.commit()
            db.refresh(upload)

            graph.link_upload_to_field(resolved_field_id, upload.id, upload.capture_date, upload.detection_count)

            results.append(
                UploadResult(
                    upload_id=upload.id,
                    filename=file.filename or saved_path.name,
                    field_id=resolved_field_id,
                    trap_code=resolved_trap_code,
                    capture_date=upload.capture_date,
                    detection_count=upload.detection_count,
                    confidence_avg=upload.confidence_avg,
                    detections=[
                        DetectionResponse(
                            class_id=d['class_id'],
                            confidence=d['confidence'],
                            bbox_xyxy=d['bbox_xyxy'],
                        )
                        for d in detections
                    ],
                )
            )
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception(
            'Upload ingestion failed user=%s field=%s trap=%s file_count=%s',
            current_user.id,
            resolved_field_id,
            trap_id or resolved_trap_code,
            len(images),
        )
        raise HTTPException(status_code=500, detail='Upload processing failed due to internal error') from exc
    finally:
        graph.close()

    # Auto-backfill environmental data from oldest upload date for this field.
    try:
        field_for_env = db.query(FieldMap).filter(FieldMap.id == resolved_field_id).first()
        if field_for_env is not None:
            auto_start = infer_sync_start_date(db, resolved_field_id)
            if auto_start is not None:
                sync_environment_for_field(db, field_for_env, auto_start, date.today())
    except Exception:
        # Do not fail image upload when environmental sync is unavailable.
        logger.exception('Environmental sync failed for field=%s', resolved_field_id)
        pass

    return UploadBatchResponse(
        total_images=len(images),
        start_date=start_date,
        end_date=end_date,
        results=results,
    )


@router.get('/uploads', response_model=list[UploadSummary])
def list_my_uploads(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = apply_production_upload_filter(db.query(TrapUpload))
    if current_user.role != 'admin':
        query = query.filter(TrapUpload.user_id == current_user.id)
    return query.order_by(TrapUpload.created_at.desc()).limit(200).all()


@router.get('/model-stats')
def model_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    settings = get_settings()
    metrics_path = Path(settings.model_metrics_path)
    metrics_payload: dict = {}
    if metrics_path.exists() and metrics_path.is_file():
        try:
            metrics_payload = json.loads(metrics_path.read_text(encoding='utf-8'))
        except Exception:
            metrics_payload = {}

    totals_query = db.query(
        func.count(TrapUpload.id).label('uploads'),
        func.coalesce(func.sum(TrapUpload.detection_count), 0).label('detections'),
        func.coalesce(func.avg(TrapUpload.confidence_avg), 0.0).label('avg_confidence'),
    )
    totals = apply_production_upload_filter(totals_query).one()

    return {
        'model': {
            'weights_file': Path(settings.model_weights_path).name,
            'weights_path': settings.model_weights_path,
            'confidence_threshold': settings.model_confidence,
            'image_size': settings.model_image_size,
        },
        'evaluation': {
            'precision': metrics_payload.get('precision'),
            'recall': metrics_payload.get('recall'),
            'map50': metrics_payload.get('mAP50'),
            'map50_95': metrics_payload.get('mAP50_95', metrics_payload.get('mAP50-95')),
            'notes': metrics_payload.get(
                'notes',
                (
                    'Loaded offline validation metrics from model_metrics.json.'
                    if metrics_payload
                    else 'No offline evaluation metrics file found yet. Add model_metrics.json to show benchmark quality.'
                ),
            ),
        },
        'production_observed': {
            'total_uploads': int(totals.uploads or 0),
            'total_detections': int(totals.detections or 0),
            'average_upload_confidence': round(float(totals.avg_confidence or 0.0), 4),
        },
    }


@router.post('/exploratory-chat')
def exploratory_chat(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    question = str(payload.get('question', '')).strip()
    if not question:
        raise HTTPException(status_code=400, detail='question is required')

    requested_field_id = payload.get('field_id')
    requested_year_raw = payload.get('year')
    requested_year: int | None = None
    if requested_year_raw not in (None, '', 'all'):
        requested_year = int(requested_year_raw)
        if requested_year < 2000 or requested_year > 2100:
            raise HTTPException(status_code=400, detail='year must be between 2000 and 2100')
    all_data = bool(payload.get('all_data', True))
    weeks = int(payload.get('weeks', 26))
    weeks = max(1, min(520, weeks))

    selected_field: FieldMap | None = None
    if requested_field_id:
        selected_field = db.query(FieldMap).filter(FieldMap.id == str(requested_field_id)).first()
        if selected_field is None:
            raise HTTPException(status_code=404, detail='Field not found')
        if current_user.role != 'admin' and selected_field.owner_user_id != current_user.id:
            raise HTTPException(status_code=403, detail='Forbidden')

    base_upload_query = apply_production_upload_filter(db.query(TrapUpload))
    if current_user.role != 'admin':
        base_upload_query = base_upload_query.filter(TrapUpload.user_id == current_user.id)
    if selected_field is not None:
        base_upload_query = base_upload_query.filter(TrapUpload.field_id == selected_field.id)
    if requested_year is not None:
        base_upload_query = base_upload_query.filter(extract('year', TrapUpload.capture_date) == requested_year)

    totals = base_upload_query.with_entities(
        func.count(TrapUpload.id).label('uploads'),
        func.coalesce(func.sum(TrapUpload.detection_count), 0).label('detections'),
        func.coalesce(func.avg(TrapUpload.confidence_avg), 0.0).label('avg_confidence'),
    ).one()

    by_field_query = db.query(
        TrapUpload.field_id.label('field_id'),
        func.count(TrapUpload.id).label('uploads'),
        func.coalesce(func.sum(TrapUpload.detection_count), 0).label('detections'),
    )
    if current_user.role != 'admin':
        by_field_query = by_field_query.filter(TrapUpload.user_id == current_user.id)
    if requested_year is not None:
        by_field_query = by_field_query.filter(extract('year', TrapUpload.capture_date) == requested_year)
    by_field = (
        by_field_query.group_by(TrapUpload.field_id)
        .order_by(func.sum(TrapUpload.detection_count).desc())
        .limit(8)
        .all()
    )

    by_trap_query = db.query(
        TrapUpload.trap_code.label('trap_code'),
        func.count(TrapUpload.id).label('uploads'),
        func.coalesce(func.sum(TrapUpload.detection_count), 0).label('detections'),
    )
    if current_user.role != 'admin':
        by_trap_query = by_trap_query.filter(TrapUpload.user_id == current_user.id)
    if selected_field is not None:
        by_trap_query = by_trap_query.filter(TrapUpload.field_id == selected_field.id)
    if requested_year is not None:
        by_trap_query = by_trap_query.filter(extract('year', TrapUpload.capture_date) == requested_year)
    by_trap = (
        by_trap_query.group_by(TrapUpload.trap_code)
        .order_by(func.sum(TrapUpload.detection_count).desc())
        .limit(8)
        .all()
    )

    recent_uploads = (
        base_upload_query.order_by(TrapUpload.created_at.desc())
        .limit(20)
        .all()
    )

    latest_upload_date = base_upload_query.with_entities(func.max(TrapUpload.capture_date)).scalar()
    if latest_upload_date is not None:
        if all_data:
            earliest_upload_date = base_upload_query.with_entities(func.min(TrapUpload.capture_date)).scalar()
            window_start = earliest_upload_date or latest_upload_date
        else:
            window_start = latest_upload_date - date.resolution * (weeks * 7 - 1)
    else:
        window_start = None

    weekly_population_query = db.query(
        func.date_trunc('week', TrapUpload.capture_date).label('week_start'),
        func.count(TrapUpload.id).label('uploads'),
        func.coalesce(func.avg(TrapUpload.detection_count), 0.0).label('avg_population'),
        func.coalesce(func.sum(TrapUpload.detection_count), 0).label('total_population'),
    )
    if current_user.role != 'admin':
        weekly_population_query = weekly_population_query.filter(TrapUpload.user_id == current_user.id)
    if selected_field is not None:
        weekly_population_query = weekly_population_query.filter(TrapUpload.field_id == selected_field.id)
    if requested_year is not None:
        weekly_population_query = weekly_population_query.filter(extract('year', TrapUpload.capture_date) == requested_year)
    if window_start is not None and latest_upload_date is not None:
        weekly_population_query = weekly_population_query.filter(
            and_(TrapUpload.capture_date >= window_start, TrapUpload.capture_date <= latest_upload_date)
        )
    weekly_population = (
        weekly_population_query.group_by(func.date_trunc('week', TrapUpload.capture_date))
        .order_by(func.date_trunc('week', TrapUpload.capture_date))
        .all()
    )

    weekly_weather = []
    if selected_field is not None:
        weather_query = db.query(
            func.date_trunc('week', TrapUpload.capture_date).label('week_start'),
            func.coalesce(func.avg(FieldMap.area_m2), 0.0).label('field_area_m2'),
        ).filter(TrapUpload.field_id == selected_field.id)
        if window_start is not None and latest_upload_date is not None:
            weather_query = weather_query.filter(
                and_(TrapUpload.capture_date >= window_start, TrapUpload.capture_date <= latest_upload_date)
            )
        _ = weather_query

        from app.models import EnvironmentalDaily  # local import to avoid broad module-level changes

        weekly_weather_rows = db.query(
            func.date_trunc('week', EnvironmentalDaily.observation_date).label('week_start'),
            func.coalesce(func.avg(EnvironmentalDaily.temperature_mean_c), 0.0).label('temp_avg'),
            func.coalesce(func.sum(EnvironmentalDaily.precipitation_mm), 0.0).label('rain_sum'),
            func.coalesce(func.avg(EnvironmentalDaily.gdd_base10_c), 0.0).label('gdd_avg'),
            func.coalesce(func.avg(EnvironmentalDaily.water_deficit_mm), 0.0).label('deficit_avg'),
            func.coalesce(func.avg(EnvironmentalDaily.heat_stress_c), 0.0).label('heat_stress_avg'),
        ).filter(EnvironmentalDaily.field_id == selected_field.id)
        if requested_year is not None:
            weekly_weather_rows = weekly_weather_rows.filter(extract('year', EnvironmentalDaily.observation_date) == requested_year)
        if window_start is not None and latest_upload_date is not None:
            weekly_weather_rows = weekly_weather_rows.filter(
                and_(
                    EnvironmentalDaily.observation_date >= window_start,
                    EnvironmentalDaily.observation_date <= latest_upload_date,
                )
            )
        weekly_weather = (
            weekly_weather_rows.group_by(func.date_trunc('week', EnvironmentalDaily.observation_date))
            .order_by(func.date_trunc('week', EnvironmentalDaily.observation_date))
            .all()
        )

    context_payload = {
        'scope': (
            f"field:{selected_field.id}" if selected_field is not None else ('all' if current_user.role == 'admin' else 'user-only')
        ),
        'field': (
            {
                'id': selected_field.id,
                'name': selected_field.name,
                'area_m2': selected_field.area_m2,
            }
            if selected_field is not None
            else None
        ),
        'range': {
            'all_data': all_data,
            'year': requested_year,
            'weeks': weeks,
            'start_date': str(window_start) if window_start else None,
            'end_date': str(latest_upload_date) if latest_upload_date else None,
        },
        'totals': {
            'uploads': int(totals.uploads or 0),
            'detections': int(totals.detections or 0),
            'avg_confidence': round(float(totals.avg_confidence or 0.0), 4),
        },
        'by_field': [
            {'field_id': row.field_id, 'uploads': int(row.uploads or 0), 'detections': int(row.detections or 0)}
            for row in by_field
        ],
        'by_trap': [
            {'trap_code': row.trap_code, 'uploads': int(row.uploads or 0), 'detections': int(row.detections or 0)}
            for row in by_trap
        ],
        'recent_uploads': [
            {
                'id': row.id,
                'field_id': row.field_id,
                'trap_code': row.trap_code,
                'capture_date': str(row.capture_date),
                'detection_count': row.detection_count,
            }
            for row in recent_uploads
        ],
        'weekly_population': [
            {
                'week_start': row.week_start.date().isoformat() if hasattr(row.week_start, 'date') else str(row.week_start)[:10],
                'uploads': int(row.uploads or 0),
                'avg_population': round(float(row.avg_population or 0.0), 3),
                'total_population': int(row.total_population or 0),
            }
            for row in weekly_population
        ],
        'weekly_weather': [
            {
                'week_start': row.week_start.date().isoformat() if hasattr(row.week_start, 'date') else str(row.week_start)[:10],
                'temp_avg': round(float(row.temp_avg or 0.0), 3),
                'rain_sum': round(float(row.rain_sum or 0.0), 3),
                'gdd_avg': round(float(row.gdd_avg or 0.0), 3),
                'deficit_avg': round(float(row.deficit_avg or 0.0), 3),
                'heat_stress_avg': round(float(row.heat_stress_avg or 0.0), 3),
            }
            for row in weekly_weather
        ],
    }

    settings = get_settings()
    used_openai = False
    answer = ''
    provider_error = ''

    if settings.openai_api_key:
        try:
            used_openai = True
            response = requests.post(
                'https://api.openai.com/v1/responses',
                headers={
                    'Authorization': f'Bearer {settings.openai_api_key}',
                    'Content-Type': 'application/json',
                },
                json={
                    'model': settings.openai_chat_model,
                    'input': [
                        {
                            'role': 'system',
                            'content': (
                            'You are a concise exploratory data analysis assistant for insect trap monitoring. '
                                'Answer only from provided data context. If unknown, say so. '
                                'Use specific numbers and date ranges from the context.'
                            ),
                        },
                        {
                            'role': 'user',
                            'content': (
                                f'Data context JSON:\n{json.dumps(context_payload)}\n\n'
                                f'Question:\n{question}'
                            ),
                        },
                    ],
                },
                timeout=30,
            )
            response.raise_for_status()
            payload_json = response.json()
            answer = payload_json.get('output_text', '').strip()
            if not answer:
                output_blocks = payload_json.get('output', []) or []
                chunks: list[str] = []
                for block in output_blocks:
                    for content in block.get('content', []) or []:
                        text_value = content.get('text')
                        if text_value:
                            chunks.append(text_value)
                answer = '\n'.join(chunks).strip()
            if not answer:
                answer = 'No textual output was returned by model.'
        except Exception as exc:
            provider_error = str(exc)
            used_openai = False

    if not used_openai:
        answer = (
            f"Current scope is '{context_payload['scope']}'. "
            f"Total uploads: {context_payload['totals']['uploads']}, total detections: {context_payload['totals']['detections']}, "
            f"average confidence: {context_payload['totals']['avg_confidence']}. "
            f"Top trap by detections: {context_payload['by_trap'][0]['trap_code'] if context_payload['by_trap'] else 'n/a'}. "
            f"Your question was: '{question}'. "
            'For deeper natural-language analysis, set OPENAI_API_KEY in backend .env.'
        )

    return {
        'answer': answer,
        'used_openai': used_openai,
        'provider_error': provider_error,
        'context': {
            'totals': context_payload['totals'],
            'top_fields': context_payload['by_field'][:3],
            'top_traps': context_payload['by_trap'][:3],
        },
        'full_context': context_payload,
    }


def _line_chart_svg(title: str, labels: list[str], values: list[float], y_label: str, stroke: str) -> str:
    if not labels or not values:
        return '<p>No data available for this chart.</p>'
    width = 760
    height = 280
    margin_left = 56
    margin_right = 16
    margin_top = 16
    margin_bottom = 52
    inner_w = width - margin_left - margin_right
    inner_h = height - margin_top - margin_bottom
    raw_min = min(values) if values else 0.0
    raw_max = max(values) if values else 1.0
    span = max(raw_max - raw_min, 1e-6)
    pad = span * 0.08
    min_v = raw_min - pad
    max_v = raw_max + pad
    if max_v == min_v:
        min_v -= 1.0
        max_v += 1.0

    def x_for(idx: int) -> float:
        if len(values) <= 1:
            return float(margin_left)
        return margin_left + (idx * inner_w / (len(values) - 1))

    def y_for(val: float) -> float:
        return margin_top + ((max_v - val) / (max_v - min_v)) * inner_h

    points = ' '.join(f'{x_for(i):.2f},{y_for(v):.2f}' for i, v in enumerate(values))
    y_ticks = [min_v + (max_v - min_v) * (i / 5.0) for i in range(6)]
    tick_lines = ''.join(
        f'<line x1="{margin_left}" y1="{y_for(t):.2f}" x2="{width - margin_right}" y2="{y_for(t):.2f}" stroke="#e2e8f0" />'
        f'<text x="{margin_left - 8}" y="{y_for(t) + 4:.2f}" text-anchor="end" fill="#475569" font-size="11">{t:.1f}</text>'
        for t in y_ticks
    )
    x_labels = ''.join(
        f'<text x="{x_for(i):.2f}" y="{height - margin_bottom + 14}" text-anchor="middle" fill="#64748b" font-size="10">{escape(labels[i])}</text>'
        for i in range(len(labels))
    )
    circles = ''.join(
        f'<circle cx="{x_for(i):.2f}" cy="{y_for(v):.2f}" r="3" fill="{stroke}"><title>{escape(labels[i])}: {v:.2f}</title></circle>'
        for i, v in enumerate(values)
    )
    return (
        f'<div class="chart-card"><h3>{escape(title)}</h3>'
        f'<svg viewBox="0 0 {width} {height}" class="chart-svg">{tick_lines}'
        f'<line x1="{margin_left}" y1="{height - margin_bottom}" x2="{width - margin_right}" y2="{height - margin_bottom}" stroke="#64748b" stroke-width="1.2" />'
        f'<line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{height - margin_bottom}" stroke="#64748b" stroke-width="1.2" />'
        f'<polyline fill="none" stroke="{stroke}" stroke-width="3" points="{points}" />{circles}{x_labels}'
        f'<text x="{margin_left + inner_w / 2:.2f}" y="{height - 10}" text-anchor="middle" fill="#334155" font-size="12">Week</text>'
        f'<text x="14" y="{margin_top + inner_h / 2:.2f}" text-anchor="middle" transform="rotate(-90, 14, {margin_top + inner_h / 2:.2f})" fill="#334155" font-size="12">{escape(y_label)}</text>'
        '</svg></div>'
    )


def _scatter_svg(title: str, points: list[dict]) -> str:
    if not points:
        return '<p>No overlapping insect/temperature weekly data available.</p>'
    width = 760
    height = 280
    margin_left = 56
    margin_right = 16
    margin_top = 16
    margin_bottom = 52
    inner_w = width - margin_left - margin_right
    inner_h = height - margin_top - margin_bottom

    x_vals = [float(p['temp_avg']) for p in points]
    y_vals = [float(p['avg_population']) for p in points]
    x_min, x_max = min(x_vals), max(x_vals)
    y_min, y_max = min(y_vals), max(y_vals)
    if x_min == x_max:
        x_max += 1.0
    if y_min == y_max:
        y_max += 1.0
    x_span = max(x_max - x_min, 1e-6)
    y_span = max(y_max - y_min, 1e-6)
    x_pad = x_span * 0.08
    y_pad = y_span * 0.08
    x_min -= x_pad
    x_max += x_pad
    y_min -= y_pad
    y_max += y_pad

    def x_for(v: float) -> float:
        return margin_left + ((v - x_min) / (x_max - x_min)) * inner_w

    def y_for(v: float) -> float:
        return margin_top + ((y_max - v) / (y_max - y_min)) * inner_h

    x_ticks = [x_min + (x_max - x_min) * (i / 5.0) for i in range(6)]
    y_ticks = [y_min + (y_max - y_min) * (i / 5.0) for i in range(6)]
    tick_lines = ''.join(
        f'<line x1="{x_for(x):.2f}" y1="{margin_top}" x2="{x_for(x):.2f}" y2="{height - margin_bottom}" stroke="#e2e8f0" />'
        for x in x_ticks
    ) + ''.join(
        f'<line x1="{margin_left}" y1="{y_for(y):.2f}" x2="{width - margin_right}" y2="{y_for(y):.2f}" stroke="#e2e8f0" />'
        for y in y_ticks
    )
    x_tick_labels = ''.join(
        f'<text x="{x_for(x):.2f}" y="{height - margin_bottom + 14}" text-anchor="middle" fill="#64748b" font-size="10">{x:.1f}</text>'
        for x in x_ticks
    )
    y_tick_labels = ''.join(
        f'<text x="{margin_left - 8}" y="{y_for(y) + 4:.2f}" text-anchor="end" fill="#475569" font-size="11">{y:.1f}</text>'
        for y in y_ticks
    )
    points_svg = ''.join(
        f'<circle cx="{x_for(float(p["temp_avg"])):.2f}" cy="{y_for(float(p["avg_population"])):.2f}" r="4" fill="#2563eb">'
        f'<title>{escape(p["week_start"])}: temp={float(p["temp_avg"]):.2f} C, avg={float(p["avg_population"]):.2f}</title></circle>'
        for p in points
    )
    return (
        f'<div class="chart-card"><h3>{escape(title)}</h3>'
        f'<svg viewBox="0 0 {width} {height}" class="chart-svg">'
        f'{tick_lines}{x_tick_labels}{y_tick_labels}'
        f'<line x1="{margin_left}" y1="{height - margin_bottom}" x2="{width - margin_right}" y2="{height - margin_bottom}" stroke="#64748b" stroke-width="1.2" />'
        f'<line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{height - margin_bottom}" stroke="#64748b" stroke-width="1.2" />'
        f'{points_svg}'
        f'<text x="{margin_left + inner_w / 2:.2f}" y="{height - 10}" text-anchor="middle" fill="#334155" font-size="12">Temperature (C)</text>'
        f'<text x="14" y="{margin_top + inner_h / 2:.2f}" text-anchor="middle" transform="rotate(-90, 14, {margin_top + inner_h / 2:.2f})" fill="#334155" font-size="12">Avg detections per image</text>'
        '</svg></div>'
    )


def _bar_chart_svg(title: str, labels: list[str], values: list[float], y_label: str, color: str) -> str:
    if not labels or not values:
        return '<p>No data available for this chart.</p>'
    width = 760
    height = 280
    margin_left = 56
    margin_right = 16
    margin_top = 16
    margin_bottom = 52
    inner_w = width - margin_left - margin_right
    inner_h = height - margin_top - margin_bottom
    max_v = max(max(values), 1e-6)
    bar_span = inner_w / max(len(values), 1)
    bar_w = max(8.0, bar_span * 0.7)

    def x_for(idx: int) -> float:
        return margin_left + (idx * bar_span) + (bar_span - bar_w) / 2.0

    def y_for(v: float) -> float:
        return margin_top + ((max_v - v) / max_v) * inner_h

    y_ticks = [max_v * (i / 5.0) for i in range(6)]
    tick_lines = ''.join(
        f'<line x1="{margin_left}" y1="{y_for(t):.2f}" x2="{width - margin_right}" y2="{y_for(t):.2f}" stroke="#e2e8f0" />'
        f'<text x="{margin_left - 8}" y="{y_for(t) + 4:.2f}" text-anchor="end" fill="#475569" font-size="11">{t:.1f}</text>'
        for t in y_ticks
    )
    bars = ''.join(
        f'<rect x="{x_for(i):.2f}" y="{y_for(v):.2f}" width="{bar_w:.2f}" height="{(margin_top + inner_h - y_for(v)):.2f}" fill="{color}">'
        f'<title>{escape(labels[i])}: {v:.2f}</title></rect>'
        for i, v in enumerate(values)
    )
    x_labels = ''.join(
        f'<text x="{x_for(i) + bar_w / 2:.2f}" y="{height - margin_bottom + 14}" text-anchor="middle" fill="#64748b" font-size="10">{escape(labels[i])}</text>'
        for i in range(len(labels))
    )
    return (
        f'<div class="chart-card"><h3>{escape(title)}</h3>'
        f'<svg viewBox="0 0 {width} {height}" class="chart-svg">{tick_lines}'
        f'<line x1="{margin_left}" y1="{height - margin_bottom}" x2="{width - margin_right}" y2="{height - margin_bottom}" stroke="#64748b" stroke-width="1.2" />'
        f'<line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{height - margin_bottom}" stroke="#64748b" stroke-width="1.2" />'
        f'{bars}{x_labels}'
        f'<text x="{margin_left + inner_w / 2:.2f}" y="{height - 10}" text-anchor="middle" fill="#334155" font-size="12">Category</text>'
        f'<text x="14" y="{margin_top + inner_h / 2:.2f}" text-anchor="middle" transform="rotate(-90, 14, {margin_top + inner_h / 2:.2f})" fill="#334155" font-size="12">{escape(y_label)}</text>'
        '</svg></div>'
    )


def _yearly_week_comparison_svg(title: str, rows: list[dict]) -> str:
    by_year: dict[int, dict[int, float]] = defaultdict(dict)
    for row in rows:
        try:
            parsed = date.fromisoformat(str(row['week_start']))
        except Exception:
            continue
        iso_week = int(parsed.isocalendar().week)
        by_year[int(parsed.year)][iso_week] = float(row['avg_population'])
    years = sorted(by_year.keys())
    if len(years) < 2:
        return '<p>Not enough yearly series to compare.</p>'

    week_values = sorted({week for series in by_year.values() for week in series.keys()})
    if len(week_values) < 2:
        return '<p>Not enough weekly points to compare years.</p>'

    width = 760
    height = 280
    margin_left = 56
    margin_right = 16
    margin_top = 16
    margin_bottom = 52
    inner_w = width - margin_left - margin_right
    inner_h = height - margin_top - margin_bottom
    all_points = [v for series in by_year.values() for v in series.values()]
    min_v = min(all_points)
    max_v = max(all_points)
    if min_v == max_v:
        max_v += 1.0
    span = max(max_v - min_v, 1e-6)
    min_v -= span * 0.08
    max_v += span * 0.08

    def x_for(week: int) -> float:
        if len(week_values) <= 1:
            return float(margin_left)
        idx = week_values.index(week)
        return margin_left + (idx * inner_w / (len(week_values) - 1))

    def y_for(v: float) -> float:
        return margin_top + ((max_v - v) / (max_v - min_v)) * inner_h

    y_ticks = [min_v + (max_v - min_v) * (i / 5.0) for i in range(6)]
    tick_lines = ''.join(
        f'<line x1="{margin_left}" y1="{y_for(t):.2f}" x2="{width - margin_right}" y2="{y_for(t):.2f}" stroke="#e2e8f0" />'
        f'<text x="{margin_left - 8}" y="{y_for(t) + 4:.2f}" text-anchor="end" fill="#475569" font-size="11">{t:.1f}</text>'
        for t in y_ticks
    )
    color_palette = ['#1e3a8a', '#1d4ed8', '#2563eb', '#3b82f6', '#60a5fa']
    series_svg: list[str] = []
    legend_svg: list[str] = []
    for idx, year in enumerate(years):
        color = color_palette[idx % len(color_palette)]
        series = by_year[year]
        points = ' '.join(f'{x_for(week):.2f},{y_for(series[week]):.2f}' for week in week_values if week in series)
        circles = ''.join(
            f'<circle cx="{x_for(week):.2f}" cy="{y_for(series[week]):.2f}" r="3" fill="{color}">'
            f'<title>{year} week {week}: {series[week]:.2f}</title></circle>'
            for week in week_values
            if week in series
        )
        if points:
            series_svg.append(f'<polyline fill="none" stroke="{color}" stroke-width="2.5" points="{points}" />{circles}')
        legend_y = margin_top + 14 + idx * 14
        legend_svg.append(
            f'<rect x="{width - margin_right - 135}" y="{legend_y - 9}" width="10" height="10" fill="{color}" />'
            f'<text x="{width - margin_right - 120}" y="{legend_y}" fill="#334155" font-size="11">{year}</text>'
        )

    x_label_step = max(1, len(week_values) // 8)
    x_labels = ''.join(
        f'<text x="{x_for(week):.2f}" y="{height - margin_bottom + 14}" text-anchor="middle" fill="#64748b" font-size="10">W{week}</text>'
        for i, week in enumerate(week_values)
        if i % x_label_step == 0 or i == len(week_values) - 1
    )
    return (
        f'<div class="chart-card"><h3>{escape(title)}</h3>'
        f'<svg viewBox="0 0 {width} {height}" class="chart-svg">{tick_lines}'
        f'<line x1="{margin_left}" y1="{height - margin_bottom}" x2="{width - margin_right}" y2="{height - margin_bottom}" stroke="#64748b" stroke-width="1.2" />'
        f'<line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{height - margin_bottom}" stroke="#64748b" stroke-width="1.2" />'
        f'{"".join(series_svg)}{x_labels}{"".join(legend_svg)}'
        f'<text x="{margin_left + inner_w / 2:.2f}" y="{height - 10}" text-anchor="middle" fill="#334155" font-size="12">ISO week</text>'
        f'<text x="14" y="{margin_top + inner_h / 2:.2f}" text-anchor="middle" transform="rotate(-90, 14, {margin_top + inner_h / 2:.2f})" fill="#334155" font-size="12">Avg detections per image</text>'
        '</svg></div>'
    )


def _detect_question_intents(question: str) -> dict:
    q = question.lower()
    compare_keywords = ('compare', 'comparison', 'versus', 'vs', 'difference', 'between', 'year')
    weather_keywords = ('weather', 'temperature', 'temp', 'rain', 'precip', 'gdd', 'deficit', 'heat')
    trap_keywords = ('trap', 'row', 'side', 'position', 'map')
    explicit_years = re.findall(r'\b20\d{2}\b', q)
    return {
        'compare': any(word in q for word in compare_keywords) or len(set(explicit_years)) >= 2,
        'weather': any(word in q for word in weather_keywords),
        'trap': any(word in q for word in trap_keywords),
    }


def _render_exploratory_report_html(question: str, answer: str, context: dict) -> str:
    field_name = (context.get('field') or {}).get('name') or 'All Accessible Fields'
    range_data = context.get('range') or {}
    pop_rows = context.get('weekly_population') or []
    weather_rows = context.get('weekly_weather') or []
    weather_by_week = {row['week_start']: row for row in weather_rows}
    joined_rows = sorted([
        {
            'week_start': row['week_start'],
            'avg_population': float(row['avg_population']),
            'total_population': int(row['total_population']),
            'uploads': int(row['uploads']),
            'temp_avg': (
                float((weather_by_week.get(row['week_start']) or {}).get('temp_avg'))
                if (weather_by_week.get(row['week_start']) or {}).get('temp_avg') is not None
                else None
            ),
            'rain_sum': (
                float((weather_by_week.get(row['week_start']) or {}).get('rain_sum'))
                if (weather_by_week.get(row['week_start']) or {}).get('rain_sum') is not None
                else None
            ),
            'gdd_avg': (
                float((weather_by_week.get(row['week_start']) or {}).get('gdd_avg'))
                if (weather_by_week.get(row['week_start']) or {}).get('gdd_avg') is not None
                else None
            ),
            'deficit_avg': (
                float((weather_by_week.get(row['week_start']) or {}).get('deficit_avg'))
                if (weather_by_week.get(row['week_start']) or {}).get('deficit_avg') is not None
                else None
            ),
        }
        for row in pop_rows
    ], key=lambda row: row['week_start'])
    intents = _detect_question_intents(question)
    scatter_rows = [row for row in joined_rows if row['temp_avg'] is not None]
    graph_checks: list[str] = []
    chart_blocks: list[str] = []

    if len(joined_rows) >= 2:
        chart_blocks.append(
            _line_chart_svg(
                'Population Trend by Week',
                [row['week_start'][5:] for row in joined_rows],
                [float(row['avg_population']) for row in joined_rows],
                'Avg detections per image',
                '#1d4ed8',
            )
        )
        graph_checks.append('Population trend chart: ok')
    else:
        graph_checks.append('Population trend chart: insufficient data')

    years_present = sorted({int(row['week_start'][:4]) for row in joined_rows if isinstance(row.get('week_start'), str) and len(row['week_start']) >= 4})
    if intents['compare']:
        if len(years_present) >= 2:
            chart_blocks.append(_yearly_week_comparison_svg('Year Comparison: Weekly Avg Detections per Image', joined_rows))
            graph_checks.append('Year comparison chart: ok')
            year_totals: dict[int, dict[str, float]] = {}
            for row in joined_rows:
                year = int(str(row['week_start'])[:4])
                bucket = year_totals.setdefault(year, {'total': 0.0, 'uploads': 0.0})
                bucket['total'] += float(row['total_population'])
                bucket['uploads'] += float(row['uploads'])
            ordered_years = sorted(year_totals.keys())
            chart_blocks.append(
                _bar_chart_svg(
                    'Yearly Total Detections',
                    [str(year) for year in ordered_years],
                    [float(year_totals[year]['total']) for year in ordered_years],
                    'Detections',
                    '#2563eb',
                )
            )
            chart_blocks.append(
                _bar_chart_svg(
                    'Yearly Avg Detections per Image',
                    [str(year) for year in ordered_years],
                    [
                        float(year_totals[year]['total']) / float(year_totals[year]['uploads'])
                        if float(year_totals[year]['uploads']) > 0
                        else 0.0
                        for year in ordered_years
                    ],
                    'Avg detections per image',
                    '#2563eb',
                )
            )
            graph_checks.append('Yearly summary charts: ok')
        else:
            graph_checks.append('Year comparison chart: insufficient yearly series')

    if intents['weather']:
        if len(scatter_rows) >= 2:
            chart_blocks.append(
                _line_chart_svg(
                    'Average Temperature by Week',
                    [row['week_start'][5:] for row in scatter_rows],
                    [float(row['temp_avg']) for row in scatter_rows],
                    'Temperature (C)',
                    '#2563eb',
                )
            )
            chart_blocks.append(_scatter_svg('Detections vs Temperature (Weekly)', scatter_rows))
            graph_checks.append('Weather charts: ok')
        else:
            graph_checks.append('Weather charts: insufficient matched weather data')
        rain_rows = [row for row in joined_rows if row['rain_sum'] is not None]
        if len(rain_rows) >= 2:
            chart_blocks.append(
                _line_chart_svg(
                    'Rainfall by Week',
                    [row['week_start'][5:] for row in rain_rows],
                    [float(row['rain_sum']) for row in rain_rows],
                    'Rain (mm)',
                    '#3b82f6',
                )
            )

    if intents['trap']:
        trap_rows = context.get('by_trap') or []
        if trap_rows:
            labels = [str(row.get('trap_code', '-')) for row in trap_rows[:12]]
            totals = [float(row.get('detections') or 0.0) for row in trap_rows[:12]]
            avg_values = [
                (float(row.get('detections') or 0.0) / float(row.get('uploads') or 1.0))
                if float(row.get('uploads') or 0.0) > 0
                else 0.0
                for row in trap_rows[:12]
            ]
            chart_blocks.append(_bar_chart_svg('Top Traps by Total Detections', labels, totals, 'Detections', '#1d4ed8'))
            chart_blocks.append(_bar_chart_svg('Top Traps by Avg Detections per Image', labels, avg_values, 'Avg detections per image', '#2563eb'))
            graph_checks.append('Trap charts: ok')
        else:
            graph_checks.append('Trap charts: no trap-level data')

    table_rows = ''.join(
        '<tr>'
        f'<td>{escape(str(row["week_start"]))}</td>'
        f'<td>{escape(str(row["week_start"])[:4])}</td>'
        f'<td>{("{:.3f}".format(float(row["temp_avg"])) if row["temp_avg"] is not None else "-")}</td>'
        f'<td>{("{:.3f}".format(float(row["rain_sum"])) if row["rain_sum"] is not None else "-")}</td>'
        f'<td>{row["avg_population"]:.3f}</td>'
        f'<td>{row["total_population"]}</td>'
        f'<td>{row["uploads"]}</td>'
        '</tr>'
        for row in joined_rows
    )
    checks_html = ''.join(f'<li>{escape(item)}</li>' for item in graph_checks)
    charts_html = ''.join(chart_blocks) if chart_blocks else '<p>No chart available for the current data scope.</p>'
    scope_label = 'All data' if range_data.get('all_data', True) else f'Last {range_data.get("weeks", "-")} weeks'
    if range_data.get('year') is not None:
        scope_label = f'Year {range_data.get("year")}'

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Exploratory Analysis Report</title>
  <style>
    body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 24px; color: #0f172a; background: linear-gradient(180deg, #eff6ff 0%, #f8fbff 100%); }}
    .card {{ background: #fff; border: 1px solid #bfdbfe; border-radius: 12px; padding: 16px; margin-bottom: 16px; box-shadow: 0 6px 16px rgba(30, 64, 175, 0.07); }}
    .meta {{ display: grid; grid-template-columns: repeat(2, minmax(220px, 1fr)); gap: 8px; }}
    .charts {{ display: grid; grid-template-columns: 1fr; gap: 16px; }}
    .chart-card {{ background: #fff; border: 1px solid #bfdbfe; border-radius: 12px; padding: 12px; box-shadow: 0 4px 12px rgba(37, 99, 235, 0.06); }}
    .chart-svg {{ width: 100%; height: auto; background: linear-gradient(180deg, #eff6ff 0%, #ffffff 100%); border-radius: 8px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border: 1px solid #e2e8f0; padding: 8px; text-align: left; font-size: 13px; }}
    th {{ background: #f1f5f9; }}
    h1, h2, h3 {{ margin: 0 0 10px 0; }}
    p {{ margin: 6px 0; line-height: 1.4; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Exploratory Analysis Report</h1>
    <div class="meta">
      <p><strong>Field:</strong> {escape(str(field_name))}</p>
      <p><strong>Data scope:</strong> {escape(str(scope_label))}</p>
      <p><strong>Start date:</strong> {escape(str(range_data.get('start_date', '-')))}</p>
      <p><strong>End date:</strong> {escape(str(range_data.get('end_date', '-')))}</p>
      <p><strong>Question:</strong> {escape(question)}</p>
      <p><strong>Generated:</strong> {date.today().isoformat()}</p>
    </div>
  </div>
  <div class="card">
    <h2>Assistant Summary</h2>
    <p>{escape(answer).replace(chr(10), '<br/>')}</p>
    <h3>Graph Validation</h3>
    <ul>{checks_html}</ul>
  </div>
  <div class="charts">{charts_html}</div>
  <div class="card">
    <h2>Weekly Data Table</h2>
    <table>
      <thead>
        <tr>
          <th>Week Start</th>
          <th>Year</th>
          <th>Avg Temp (C)</th>
          <th>Rain (mm)</th>
          <th>Avg Detections per Image</th>
          <th>Total Detections</th>
          <th>Uploads</th>
        </tr>
      </thead>
      <tbody>
        {table_rows}
      </tbody>
    </table>
  </div>
</body>
</html>
"""


@router.post('/exploratory-report')
def exploratory_report(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    chat_result = exploratory_chat(payload, db, current_user)
    question = str(payload.get('question', '')).strip()
    context = chat_result.get('full_context', {})
    report_html = _render_exploratory_report_html(question=question, answer=chat_result.get('answer', ''), context=context)
    field_tag = ((context.get('field') or {}).get('name') or 'all-fields').lower().replace(' ', '-')
    return {
        'answer': chat_result.get('answer', ''),
        'used_openai': chat_result.get('used_openai', False),
        'provider_error': chat_result.get('provider_error', ''),
        'context': chat_result.get('context', {}),
        'filename': f'exploratory-report-{field_tag}-{date.today().isoformat()}.html',
        'html': report_html,
    }
