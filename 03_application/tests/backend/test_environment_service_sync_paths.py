from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.services import environment_service as env


class _DummyExcluded:
    latitude = "lat"
    longitude = "lng"
    temperature_mean_c = "tm"
    temperature_max_c = "tx"
    temperature_min_c = "tn"
    precipitation_mm = "p"
    shortwave_radiation_sum_mj_m2 = "s"
    et0_fao_mm = "e"
    wind_speed_max_ms = "w"
    fetched_at = "f"
    provider = "provider"
    gdd_base10_c = "g"
    water_deficit_mm = "d"
    heat_stress_c = "h"
    light_accumulation_mj_m2 = "l"


class _DummyStmt:
    def __init__(self, values) -> None:  # noqa: ANN001
        self.values_payload = values
        self.excluded = _DummyExcluded()

    def on_conflict_do_update(self, **kwargs):  # noqa: ANN003
        return self


class _InsertFactory:
    def __call__(self, _model):  # noqa: ANN001
        class _Builder:
            def values(self, values):  # noqa: ANN001
                return _DummyStmt(values)

        return _Builder()


class FakeQuery:
    def __init__(self, all_value=None, one_value=None):
        self._all = all_value if all_value is not None else []
        self._one = one_value

    def filter(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self

    def all(self):
        return self._all

    def one(self):
        return self._one


class FakeDB:
    def __init__(self, queries: list[FakeQuery]) -> None:
        self._queries = list(queries)
        self.executed = []
        self.commits = 0

    def execute(self, stmt):  # noqa: ANN001
        self.executed.append(stmt)
        return None

    def commit(self):
        self.commits += 1

    def query(self, *args, **kwargs):  # noqa: ANN002, ANN003
        if not self._queries:
            return FakeQuery()
        return self._queries.pop(0)


def test_fetch_open_meteo_daily_success(monkeypatch) -> None:  # noqa: ANN001
    class Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "daily": {
                    "time": ["2026-01-01"],
                    "temperature_2m_mean": [12.0],
                    "temperature_2m_max": [16.0],
                    "temperature_2m_min": [8.0],
                    "precipitation_sum": [2.0],
                    "shortwave_radiation_sum": [3.0],
                    "et0_fao_evapotranspiration": [1.2],
                    "wind_speed_10m_max": [4.0],
                }
            }

    monkeypatch.setattr(env.requests, "get", lambda *args, **kwargs: Resp())
    rows = env.fetch_open_meteo_daily(52.0, 5.0, date(2026, 1, 1), date(2026, 1, 1))
    assert rows[0]["temperature_mean_c"] == 12.0


def test_upsert_source_rows_and_sync_environment(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(env, "insert", _InsertFactory())
    field = SimpleNamespace(id="field-1", polygon_geojson='[{"lat": 52.0, "lng": 5.0}, {"lat": 52.2, "lng": 5.2}]')
    source_row = SimpleNamespace(
        observation_date=date(2026, 1, 1),
        provider="open-meteo",
        temperature_mean_c=11.0,
        temperature_max_c=14.0,
        temperature_min_c=8.0,
        precipitation_mm=2.0,
        shortwave_radiation_sum_mj_m2=3.0,
        et0_fao_mm=1.0,
        wind_speed_max_ms=4.0,
    )
    db = FakeDB([FakeQuery(all_value=[source_row])])
    monkeypatch.setattr(env, "fetch_open_meteo_daily", lambda *args, **kwargs: [{"observation_date": date(2026, 1, 1)}])
    monkeypatch.setattr(env, "fetch_nasa_power_daily", lambda *args, **kwargs: [])
    monkeypatch.setattr(env, "fetch_meteostat_daily", lambda *args, **kwargs: [])

    out = env.sync_environment_for_field(db, field, date(2026, 1, 1), date(2026, 1, 2))
    assert out["inserted_or_updated"] == 1
    assert out["sources"]["open-meteo"] == 1
    assert db.commits >= 2
    assert len(db.executed) >= 2


def test_sync_environment_for_field_empty_and_infer_helpers(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(env, "insert", _InsertFactory())
    field = SimpleNamespace(id="field-1", polygon_geojson="[]")
    db = FakeDB([FakeQuery(all_value=[])])
    monkeypatch.setattr(env, "fetch_open_meteo_daily", lambda *args, **kwargs: [])
    monkeypatch.setattr(env, "fetch_nasa_power_daily", lambda *args, **kwargs: [])
    monkeypatch.setattr(env, "fetch_meteostat_daily", lambda *args, **kwargs: [])

    out = env.sync_environment_for_field(db, field, date(2026, 1, 1), date(2026, 1, 2))
    assert out["inserted_or_updated"] == 0
    assert out["latitude"] == 0.0

    class _DBForInfer:
        def query(self, *args, **kwargs):  # noqa: ANN002, ANN003
            return FakeQuery(one_value=SimpleNamespace(min_date=date(2026, 1, 2), max_date=date(2026, 1, 9)))

    infer_db = _DBForInfer()
    assert env.infer_sync_start_date(infer_db, "field-1") == date(2026, 1, 2)
    assert env.infer_sync_end_date(infer_db, "field-1") == date(2026, 1, 9)

