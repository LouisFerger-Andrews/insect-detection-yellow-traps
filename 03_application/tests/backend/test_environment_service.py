from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.services import environment_service as env


def test_field_centroid_handles_empty_and_polygon() -> None:
    empty = SimpleNamespace(polygon_geojson="[]")
    assert env.field_centroid(empty) == (0.0, 0.0)

    field = SimpleNamespace(
        polygon_geojson='[{"lat": 52.0, "lng": 5.0}, {"lat": 53.0, "lng": 6.0}]'
    )
    assert env.field_centroid(field) == (52.5, 5.5)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("12.5", 12.5),
        ("bad", None),
        (-9999, None),
    ],
)
def test_safe_float(value, expected) -> None:  # noqa: ANN001
    assert env._safe_float(value) == expected


def test_derive_computes_gdd_deficit_and_stress() -> None:
    row = {
        "temperature_mean_c": 15.0,
        "temperature_max_c": 33.0,
        "precipitation_mm": 2.0,
        "et0_fao_mm": 5.5,
        "shortwave_radiation_sum_mj_m2": 7.2,
    }
    out = env._derive(row)
    assert out["gdd_base10_c"] == 5.0
    assert out["water_deficit_mm"] == 3.5
    assert out["heat_stress_c"] == 3.0
    assert out["light_accumulation_mj_m2"] == 7.2


def test_merge_sources_by_day_applies_priority() -> None:
    day = date(2026, 4, 1)
    source_rows = [
        SimpleNamespace(
            observation_date=day,
            provider="nasa-power",
            temperature_mean_c=12.0,
            temperature_max_c=20.0,
            temperature_min_c=7.0,
            precipitation_mm=1.5,
            shortwave_radiation_sum_mj_m2=5.0,
            et0_fao_mm=None,
            wind_speed_max_ms=2.1,
        ),
        SimpleNamespace(
            observation_date=day,
            provider="open-meteo",
            temperature_mean_c=13.0,
            temperature_max_c=21.0,
            temperature_min_c=8.0,
            precipitation_mm=1.0,
            shortwave_radiation_sum_mj_m2=6.0,
            et0_fao_mm=4.0,
            wind_speed_max_ms=3.0,
        ),
    ]
    merged = env._merge_sources_by_day(source_rows)
    assert day in merged
    assert merged[day]["temperature_mean_c"] == 13.0
    assert merged[day]["et0_fao_mm"] == 4.0
    assert merged[day]["gdd_base10_c"] == 3.0


def test_fetch_nasa_power_daily_returns_empty_on_http_error(monkeypatch) -> None:  # noqa: ANN001
    class FakeResponse:
        def raise_for_status(self) -> None:
            raise env.requests.HTTPError("boom")

        def json(self):  # pragma: no cover
            return {}

    monkeypatch.setattr(env.requests, "get", lambda *args, **kwargs: FakeResponse())
    rows = env.fetch_nasa_power_daily(52.0, 5.0, date(2026, 1, 1), date(2026, 1, 2))
    assert rows == []

