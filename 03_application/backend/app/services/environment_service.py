from __future__ import annotations

import json
from datetime import date, datetime, time

import requests
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import EnvironmentalDaily, EnvironmentalSourceDaily, FieldMap, TrapUpload
from app.services.upload_visibility import apply_production_upload_filter

try:
    from meteostat import Daily, Point
except Exception:  # pragma: no cover
    Daily = None
    Point = None


PROVIDERS = ('open-meteo', 'nasa-power', 'meteostat')


def field_centroid(field: FieldMap) -> tuple[float, float]:
    polygon = json.loads(field.polygon_geojson)
    if not polygon:
        return 0.0, 0.0
    lat = sum(point['lat'] for point in polygon) / len(polygon)
    lng = sum(point['lng'] for point in polygon) / len(polygon)
    return float(lat), float(lng)


def _safe_float(value) -> float | None:
    if value is None:
        return None
    try:
        v = float(value)
        if v < -9000:
            return None
        return v
    except (TypeError, ValueError):
        return None


def _derive(row: dict) -> dict:
    t_mean = row.get('temperature_mean_c')
    t_max = row.get('temperature_max_c')
    precip = row.get('precipitation_mm')
    et0 = row.get('et0_fao_mm')
    shortwave = row.get('shortwave_radiation_sum_mj_m2')
    return {
        'gdd_base10_c': (max(0.0, t_mean - 10.0) if t_mean is not None else None),
        'water_deficit_mm': ((et0 - precip) if (et0 is not None and precip is not None) else None),
        'heat_stress_c': (max(0.0, t_max - 30.0) if t_max is not None else None),
        'light_accumulation_mj_m2': shortwave,
    }


def fetch_open_meteo_daily(lat: float, lng: float, start_date: date, end_date: date) -> list[dict]:
    response = requests.get(
        'https://archive-api.open-meteo.com/v1/archive',
        params={
            'community': 'AG',
            'latitude': lat,
            'longitude': lng,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'daily': (
                'temperature_2m_mean,temperature_2m_max,temperature_2m_min,precipitation_sum,'
                'shortwave_radiation_sum,et0_fao_evapotranspiration,wind_speed_10m_max'
            ),
            'timezone': 'UTC',
        },
        timeout=30,
    )
    response.raise_for_status()
    daily = response.json().get('daily', {})
    dates = daily.get('time', []) or []
    rows: list[dict] = []
    for idx, day_str in enumerate(dates):
        rows.append(
            {
                'observation_date': date.fromisoformat(day_str),
                'temperature_mean_c': _safe_float((daily.get('temperature_2m_mean') or [None])[idx]),
                'temperature_max_c': _safe_float((daily.get('temperature_2m_max') or [None])[idx]),
                'temperature_min_c': _safe_float((daily.get('temperature_2m_min') or [None])[idx]),
                'precipitation_mm': _safe_float((daily.get('precipitation_sum') or [None])[idx]),
                'shortwave_radiation_sum_mj_m2': _safe_float((daily.get('shortwave_radiation_sum') or [None])[idx]),
                'et0_fao_mm': _safe_float((daily.get('et0_fao_evapotranspiration') or [None])[idx]),
                'wind_speed_max_ms': _safe_float((daily.get('wind_speed_10m_max') or [None])[idx]),
            }
        )
    return rows


def fetch_nasa_power_daily(lat: float, lng: float, start_date: date, end_date: date) -> list[dict]:
    response = requests.get(
        'https://power.larc.nasa.gov/api/temporal/daily/point',
        params={
            'community': 'AG',
            'latitude': lat,
            'longitude': lng,
            'parameters': 'T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,ALLSKY_SFC_SW_DWN,WS2M',
            'start': start_date.strftime('%Y%m%d'),
            'end': end_date.strftime('%Y%m%d'),
            'format': 'JSON',
        },
        timeout=30,
    )
    try:
        response.raise_for_status()
    except requests.HTTPError:
        return []
    parameter = response.json().get('properties', {}).get('parameter', {})
    keys = sorted((parameter.get('T2M') or {}).keys())
    rows: list[dict] = []
    for key in keys:
        obs_date = datetime.strptime(key, '%Y%m%d').date()
        rows.append(
            {
                'observation_date': obs_date,
                'temperature_mean_c': _safe_float((parameter.get('T2M') or {}).get(key)),
                'temperature_max_c': _safe_float((parameter.get('T2M_MAX') or {}).get(key)),
                'temperature_min_c': _safe_float((parameter.get('T2M_MIN') or {}).get(key)),
                'precipitation_mm': _safe_float((parameter.get('PRECTOTCORR') or {}).get(key)),
                'shortwave_radiation_sum_mj_m2': _safe_float((parameter.get('ALLSKY_SFC_SW_DWN') or {}).get(key)),
                'et0_fao_mm': None,
                'wind_speed_max_ms': _safe_float((parameter.get('WS2M') or {}).get(key)),
            }
        )
    return rows


def fetch_meteostat_daily(lat: float, lng: float, start_date: date, end_date: date) -> list[dict]:
    if Daily is None or Point is None:
        return []
    location = Point(lat, lng)
    start_dt = datetime.combine(start_date, time.min)
    end_dt = datetime.combine(end_date, time.max)
    try:
        data = Daily(location, start_dt, end_dt).fetch()
    except Exception:
        return []
    rows: list[dict] = []
    if data is None or data.empty:
        return rows
    for idx, record in data.iterrows():
        obs_date = idx.date()
        rows.append(
            {
                'observation_date': obs_date,
                'temperature_mean_c': _safe_float(record.get('tavg')),
                'temperature_max_c': _safe_float(record.get('tmax')),
                'temperature_min_c': _safe_float(record.get('tmin')),
                'precipitation_mm': _safe_float(record.get('prcp')),
                'shortwave_radiation_sum_mj_m2': None,
                'et0_fao_mm': None,
                'wind_speed_max_ms': _safe_float(record.get('wspd')),
            }
        )
    return rows


def _upsert_source_rows(
    db: Session,
    field_id: str,
    lat: float,
    lng: float,
    provider: str,
    rows: list[dict],
) -> int:
    if not rows:
        return 0
    now = datetime.utcnow()
    values = [
        {
            'field_id': field_id,
            'observation_date': row['observation_date'],
            'provider': provider,
            'latitude': lat,
            'longitude': lng,
            'temperature_mean_c': row.get('temperature_mean_c'),
            'temperature_max_c': row.get('temperature_max_c'),
            'temperature_min_c': row.get('temperature_min_c'),
            'precipitation_mm': row.get('precipitation_mm'),
            'shortwave_radiation_sum_mj_m2': row.get('shortwave_radiation_sum_mj_m2'),
            'et0_fao_mm': row.get('et0_fao_mm'),
            'wind_speed_max_ms': row.get('wind_speed_max_ms'),
            'fetched_at': now,
        }
        for row in rows
    ]
    stmt = insert(EnvironmentalSourceDaily).values(values)
    stmt = stmt.on_conflict_do_update(
        constraint='uq_environmental_source_field_date_provider',
        set_={
            'latitude': stmt.excluded.latitude,
            'longitude': stmt.excluded.longitude,
            'temperature_mean_c': stmt.excluded.temperature_mean_c,
            'temperature_max_c': stmt.excluded.temperature_max_c,
            'temperature_min_c': stmt.excluded.temperature_min_c,
            'precipitation_mm': stmt.excluded.precipitation_mm,
            'shortwave_radiation_sum_mj_m2': stmt.excluded.shortwave_radiation_sum_mj_m2,
            'et0_fao_mm': stmt.excluded.et0_fao_mm,
            'wind_speed_max_ms': stmt.excluded.wind_speed_max_ms,
            'fetched_at': stmt.excluded.fetched_at,
        },
    )
    db.execute(stmt)
    return len(values)


def _merge_priority(values: list[float | None]) -> float | None:
    for value in values:
        if value is not None:
            return value
    return None


def _merge_sources_by_day(source_rows: list[EnvironmentalSourceDaily]) -> dict[date, dict]:
    grouped: dict[date, dict[str, EnvironmentalSourceDaily]] = {}
    for row in source_rows:
        grouped.setdefault(row.observation_date, {})[row.provider] = row

    merged: dict[date, dict] = {}
    for obs_date, provider_map in grouped.items():
        meteostat = provider_map.get('meteostat')
        open_meteo = provider_map.get('open-meteo')
        nasa = provider_map.get('nasa-power')

        row = {
            'temperature_mean_c': _merge_priority([getattr(meteostat, 'temperature_mean_c', None), getattr(open_meteo, 'temperature_mean_c', None), getattr(nasa, 'temperature_mean_c', None)]),
            'temperature_max_c': _merge_priority([getattr(meteostat, 'temperature_max_c', None), getattr(open_meteo, 'temperature_max_c', None), getattr(nasa, 'temperature_max_c', None)]),
            'temperature_min_c': _merge_priority([getattr(meteostat, 'temperature_min_c', None), getattr(open_meteo, 'temperature_min_c', None), getattr(nasa, 'temperature_min_c', None)]),
            'precipitation_mm': _merge_priority([getattr(meteostat, 'precipitation_mm', None), getattr(open_meteo, 'precipitation_mm', None), getattr(nasa, 'precipitation_mm', None)]),
            'shortwave_radiation_sum_mj_m2': _merge_priority([getattr(open_meteo, 'shortwave_radiation_sum_mj_m2', None), getattr(nasa, 'shortwave_radiation_sum_mj_m2', None)]),
            'et0_fao_mm': _merge_priority([getattr(open_meteo, 'et0_fao_mm', None), getattr(nasa, 'et0_fao_mm', None)]),
            'wind_speed_max_ms': _merge_priority([getattr(open_meteo, 'wind_speed_max_ms', None), getattr(meteostat, 'wind_speed_max_ms', None), getattr(nasa, 'wind_speed_max_ms', None)]),
        }
        row.update(_derive(row))
        merged[obs_date] = row
    return merged


def sync_environment_for_field(
    db: Session,
    field: FieldMap,
    start_date: date,
    end_date: date,
) -> dict:
    if start_date > end_date:
        return {'inserted_or_updated': 0, 'start_date': start_date.isoformat(), 'end_date': end_date.isoformat(), 'sources': {}}

    lat, lng = field_centroid(field)

    try:
        open_rows = fetch_open_meteo_daily(lat, lng, start_date, end_date)
    except Exception:
        open_rows = []
    try:
        nasa_rows = fetch_nasa_power_daily(lat, lng, start_date, end_date)
    except Exception:
        nasa_rows = []
    try:
        meteostat_rows = fetch_meteostat_daily(lat, lng, start_date, end_date)
    except Exception:
        meteostat_rows = []

    source_counts = {
        'open-meteo': _upsert_source_rows(db, field.id, lat, lng, 'open-meteo', open_rows),
        'nasa-power': _upsert_source_rows(db, field.id, lat, lng, 'nasa-power', nasa_rows),
        'meteostat': _upsert_source_rows(db, field.id, lat, lng, 'meteostat', meteostat_rows),
    }
    db.commit()

    source_rows = (
        db.query(EnvironmentalSourceDaily)
        .filter(
            EnvironmentalSourceDaily.field_id == field.id,
            EnvironmentalSourceDaily.observation_date >= start_date,
            EnvironmentalSourceDaily.observation_date <= end_date,
        )
        .all()
    )
    merged_by_day = _merge_sources_by_day(source_rows)

    if not merged_by_day:
        return {
            'inserted_or_updated': 0,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'latitude': lat,
            'longitude': lng,
            'sources': source_counts,
        }

    now = datetime.utcnow()
    values = []
    for obs_date, row in merged_by_day.items():
        values.append(
            {
                'field_id': field.id,
                'observation_date': obs_date,
                'provider': 'merged(open-meteo,nasa-power,meteostat)',
                'latitude': lat,
                'longitude': lng,
                'temperature_mean_c': row.get('temperature_mean_c'),
                'temperature_max_c': row.get('temperature_max_c'),
                'temperature_min_c': row.get('temperature_min_c'),
                'precipitation_mm': row.get('precipitation_mm'),
                'shortwave_radiation_sum_mj_m2': row.get('shortwave_radiation_sum_mj_m2'),
                'et0_fao_mm': row.get('et0_fao_mm'),
                'wind_speed_max_ms': row.get('wind_speed_max_ms'),
                'gdd_base10_c': row.get('gdd_base10_c'),
                'water_deficit_mm': row.get('water_deficit_mm'),
                'heat_stress_c': row.get('heat_stress_c'),
                'light_accumulation_mj_m2': row.get('light_accumulation_mj_m2'),
                'fetched_at': now,
            }
        )

    stmt = insert(EnvironmentalDaily).values(values)
    stmt = stmt.on_conflict_do_update(
        constraint='uq_environmental_field_date',
        set_={
            'provider': stmt.excluded.provider,
            'latitude': stmt.excluded.latitude,
            'longitude': stmt.excluded.longitude,
            'temperature_mean_c': stmt.excluded.temperature_mean_c,
            'temperature_max_c': stmt.excluded.temperature_max_c,
            'temperature_min_c': stmt.excluded.temperature_min_c,
            'precipitation_mm': stmt.excluded.precipitation_mm,
            'shortwave_radiation_sum_mj_m2': stmt.excluded.shortwave_radiation_sum_mj_m2,
            'et0_fao_mm': stmt.excluded.et0_fao_mm,
            'wind_speed_max_ms': stmt.excluded.wind_speed_max_ms,
            'gdd_base10_c': stmt.excluded.gdd_base10_c,
            'water_deficit_mm': stmt.excluded.water_deficit_mm,
            'heat_stress_c': stmt.excluded.heat_stress_c,
            'light_accumulation_mj_m2': stmt.excluded.light_accumulation_mj_m2,
            'fetched_at': stmt.excluded.fetched_at,
        },
    )
    db.execute(stmt)
    db.commit()

    return {
        'inserted_or_updated': len(values),
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'latitude': lat,
        'longitude': lng,
        'sources': source_counts,
    }


def infer_sync_start_date(db: Session, field_id: str) -> date | None:
    row = apply_production_upload_filter(db.query(func.min(TrapUpload.capture_date).label('min_date'))).filter(
        TrapUpload.field_id == field_id
    ).one()
    return row.min_date


def infer_sync_end_date(db: Session, field_id: str) -> date | None:
    row = apply_production_upload_filter(db.query(func.max(TrapUpload.capture_date).label('max_date'))).filter(
        TrapUpload.field_id == field_id
    ).one()
    return row.max_date
