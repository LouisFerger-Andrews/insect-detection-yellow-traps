from __future__ import annotations

import json
from uuid import uuid4

import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import FieldMap, TrapPoint, TrapUpload, User
from app.schemas.map import (
    FieldMapCreateRequest,
    FieldMapDetail,
    FieldMapSummary,
    LatLng,
    SearchResult,
    TrapCreate,
    TrapResponse,
    TrapUpdateRequest,
)
from app.utils.geo import assign_grid_codes, point_in_polygon, polygon_area_m2

router = APIRouter(prefix='/api/map', tags=['map'])


@router.get('/search', response_model=list[SearchResult])
def search_location(q: str = Query(..., min_length=2, max_length=120)) -> list[SearchResult]:
    response = requests.get(
        'https://nominatim.openstreetmap.org/search',
        params={'q': q, 'format': 'jsonv2', 'limit': 8},
        headers={'User-Agent': 'swd-monitoring-mvp/1.0 (educational project)'},
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    return [
        SearchResult(
            display_name=item.get('display_name', 'Unknown'),
            lat=float(item['lat']),
            lng=float(item['lon']),
        )
        for item in payload
    ]


@router.post('/fields', response_model=FieldMapDetail)
def create_field_map(
    body: FieldMapCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FieldMapDetail:
    polygon = [(point.lat, point.lng) for point in body.polygon]
    area_m2 = polygon_area_m2(polygon)
    if area_m2 <= 0:
        raise HTTPException(status_code=400, detail='Invalid polygon')

    field_id = f'field-{uuid4().hex[:16]}'
    field = FieldMap(
        id=field_id,
        owner_user_id=current_user.id,
        name=body.name,
        polygon_geojson=json.dumps([{'lat': p.lat, 'lng': p.lng} for p in body.polygon]),
        area_m2=area_m2,
    )
    db.add(field)
    db.flush()

    trap_rows = _create_or_replace_traps(db, field.id, polygon, body.traps)
    db.commit()
    db.refresh(field)
    return _to_field_detail(field, trap_rows)


@router.get('/fields', response_model=list[FieldMapSummary])
def list_field_maps(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[FieldMapSummary]:
    query = db.query(FieldMap)
    if current_user.role != 'admin':
        query = query.filter(FieldMap.owner_user_id == current_user.id)
    fields = query.order_by(FieldMap.created_at.desc()).all()
    return [
        FieldMapSummary(
            id=field.id,
            name=field.name,
            area_m2=field.area_m2,
            trap_count=len(field.traps),
        )
        for field in fields
    ]


@router.get('/fields/{field_id}', response_model=FieldMapDetail)
def get_field_map(
    field_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FieldMapDetail:
    field = db.query(FieldMap).filter(FieldMap.id == field_id).first()
    if field is None:
        raise HTTPException(status_code=404, detail='Field not found')
    if current_user.role != 'admin' and field.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail='Forbidden')
    return _to_field_detail(field, field.traps)


@router.post('/fields/{field_id}/traps', response_model=FieldMapDetail)
def add_trap_to_field(
    field_id: str,
    body: TrapCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FieldMapDetail:
    field = db.query(FieldMap).filter(FieldMap.id == field_id).first()
    if field is None:
        raise HTTPException(status_code=404, detail='Field not found')
    if current_user.role != 'admin' and field.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail='Forbidden')

    polygon = [(point['lat'], point['lng']) for point in json.loads(field.polygon_geojson)]
    if not point_in_polygon(body.lat, body.lng, polygon):
        raise HTTPException(status_code=400, detail='Trap must be inside field polygon')

    trap = TrapPoint(
        id=f'trap-{uuid4().hex[:16]}',
        field_id=field.id,
        code='PENDING',
        latitude=body.lat,
        longitude=body.lng,
        row_index=0,
        position_index=0,
    )
    db.add(trap)
    db.flush()

    traps = db.query(TrapPoint).filter(TrapPoint.field_id == field.id).all()
    _reassign_trap_codes(traps)
    db.commit()
    db.refresh(field)
    return _to_field_detail(field, field.traps)


@router.patch('/fields/{field_id}/traps/{trap_id}', response_model=FieldMapDetail)
def update_trap(
    field_id: str,
    trap_id: str,
    body: TrapUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FieldMapDetail:
    field = db.query(FieldMap).filter(FieldMap.id == field_id).first()
    if field is None:
        raise HTTPException(status_code=404, detail='Field not found')
    if current_user.role != 'admin' and field.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail='Forbidden')

    trap = db.query(TrapPoint).filter(TrapPoint.id == trap_id, TrapPoint.field_id == field.id).first()
    if trap is None:
        raise HTTPException(status_code=404, detail='Trap not found')

    trap.custom_name = body.name.strip()
    # Keep historical upload naming consistent for this exact trap.
    db.execute(
        TrapUpload.__table__.update()
        .where(TrapUpload.trap_id == trap.id)
        .values(trap_code=trap.custom_name)
    )
    db.commit()
    db.refresh(field)
    return _to_field_detail(field, field.traps)


def _create_or_replace_traps(
    db: Session,
    field_id: str,
    polygon: list[tuple[float, float]],
    trap_payload: list[TrapCreate],
) -> list[TrapPoint]:
    traps: list[TrapPoint] = []
    for item in trap_payload:
        if not point_in_polygon(item.lat, item.lng, polygon):
            raise HTTPException(status_code=400, detail='All traps must be inside field polygon')
        traps.append(
            TrapPoint(
                id=f'trap-{uuid4().hex[:16]}',
                field_id=field_id,
                code='PENDING',
                latitude=item.lat,
                longitude=item.lng,
                row_index=0,
                position_index=0,
            )
        )
    db.add_all(traps)
    db.flush()
    _reassign_trap_codes(traps)
    return traps


def _reassign_trap_codes(traps: list[TrapPoint]) -> None:
    assignments = assign_grid_codes([(t.id, t.latitude, t.longitude) for t in traps])
    mapping = {trap.id: trap for trap in traps}
    for trap_id, row_index, pos_index, code in assignments:
        trap = mapping[trap_id]
        trap.row_index = row_index
        trap.position_index = pos_index
        trap.code = code


def _to_field_detail(field: FieldMap, traps: list[TrapPoint]) -> FieldMapDetail:
    polygon_payload = [LatLng(**point) for point in json.loads(field.polygon_geojson)]
    trap_payload = [
        TrapResponse(
            id=trap.id,
            code=trap.code,
            name=trap.custom_name or trap.code,
            lat=trap.latitude,
            lng=trap.longitude,
            row_index=trap.row_index,
            position_index=trap.position_index,
        )
        for trap in sorted(traps, key=lambda item: (item.row_index, item.position_index))
    ]
    return FieldMapDetail(
        id=field.id,
        name=field.name,
        area_m2=field.area_m2,
        polygon=polygon_payload,
        traps=trap_payload,
    )
