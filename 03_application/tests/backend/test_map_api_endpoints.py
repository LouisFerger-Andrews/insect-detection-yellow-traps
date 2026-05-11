from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import map as map_api


@dataclass
class DummyUser:
    id: int
    role: str = "admin"


class FakeQuery:
    def __init__(self, first_value=None, all_value=None):
        self._first = first_value
        self._all = all_value if all_value is not None else []

    def filter(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self

    def order_by(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self

    def all(self):
        return self._all

    def first(self):
        return self._first


class FakeDB:
    def __init__(self, queries: list[FakeQuery]):
        self._queries = list(queries)
        self.added = []
        self.added_all = []
        self.executed = []

    def query(self, *args, **kwargs):  # noqa: ANN002, ANN003
        if not self._queries:
            return FakeQuery()
        return self._queries.pop(0)

    def add(self, obj):  # noqa: ANN001
        self.added.append(obj)

    def add_all(self, objs):  # noqa: ANN001
        self.added_all.extend(objs)

    def flush(self):
        return None

    def commit(self):
        return None

    def refresh(self, obj):  # noqa: ANN001
        return None

    def execute(self, stmt):  # noqa: ANN001
        self.executed.append(stmt)
        return None


def test_search_location_parses_response(monkeypatch: pytest.MonkeyPatch) -> None:
    class Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return [{"display_name": "A", "lat": "52.1", "lon": "5.2"}]

    monkeypatch.setattr(map_api.requests, "get", lambda *args, **kwargs: Resp())
    out = map_api.search_location("Amsterdam")
    assert out[0].display_name == "A"
    assert out[0].lat == 52.1
    assert out[0].lng == 5.2


def test_create_field_map_invalid_polygon(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(map_api, "polygon_area_m2", lambda poly: 0.0)
    body = map_api.FieldMapCreateRequest(
        name="Field",
        polygon=[map_api.LatLng(lat=52.0, lng=5.0), map_api.LatLng(lat=52.1, lng=5.0), map_api.LatLng(lat=52.1, lng=5.1)],
        traps=[],
    )
    with pytest.raises(HTTPException) as exc:
        map_api.create_field_map(body, db=FakeDB([]), current_user=DummyUser(id=1))
    assert exc.value.status_code == 400


def test_create_field_map_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(map_api, "polygon_area_m2", lambda poly: 123.4)
    monkeypatch.setattr(
        map_api,
        "_create_or_replace_traps",
        lambda db, field_id, polygon, traps: [
            SimpleNamespace(id="trap-1", code="R01-P01", custom_name=None, latitude=52.0, longitude=5.0, row_index=1, position_index=1)
        ],
    )
    body = map_api.FieldMapCreateRequest(
        name="Field",
        polygon=[map_api.LatLng(lat=52.0, lng=5.0), map_api.LatLng(lat=52.1, lng=5.0), map_api.LatLng(lat=52.1, lng=5.1)],
        traps=[],
    )
    db = FakeDB([])
    out = map_api.create_field_map(body, db=db, current_user=DummyUser(id=1))
    assert out.name == "Field"
    assert out.area_m2 == 123.4
    assert len(db.added) == 1


def test_add_trap_and_update_trap_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    field = SimpleNamespace(
        id="field-1",
        owner_user_id=1,
        polygon_geojson='[{"lat": 52.0, "lng": 5.0}, {"lat": 52.1, "lng": 5.0}, {"lat": 52.1, "lng": 5.1}]',
        traps=[],
        name="Field 1",
        area_m2=100.0,
    )
    existing_traps = [
        SimpleNamespace(id="trap-1", code="R01-P01", custom_name=None, latitude=52.01, longitude=5.01, row_index=1, position_index=1)
    ]
    trap = SimpleNamespace(id="trap-1", field_id="field-1", code="R01-P01", custom_name="Old", latitude=52.01, longitude=5.01, row_index=1, position_index=1)

    monkeypatch.setattr(map_api, "point_in_polygon", lambda lat, lng, poly: True)
    monkeypatch.setattr(map_api, "_reassign_trap_codes", lambda traps: None)

    db_add = FakeDB([FakeQuery(first_value=field), FakeQuery(all_value=existing_traps)])
    added = map_api.add_trap_to_field(
        "field-1",
        map_api.TrapCreate(lat=52.02, lng=5.02),
        db=db_add,
        current_user=DummyUser(id=1, role="admin"),
    )
    assert added.id == "field-1"

    db_update = FakeDB([FakeQuery(first_value=field), FakeQuery(first_value=trap)])
    updated = map_api.update_trap(
        "field-1",
        "trap-1",
        map_api.TrapUpdateRequest(name="Renamed"),
        db=db_update,
        current_user=DummyUser(id=1, role="admin"),
    )
    assert updated.id == "field-1"
    assert trap.custom_name == "Renamed"
    assert len(db_update.executed) == 1


def test_list_and_get_field_maps() -> None:
    f1 = SimpleNamespace(id="field-1", name="F1", area_m2=10.0, traps=[1], owner_user_id=1)
    f2 = SimpleNamespace(id="field-2", name="F2", area_m2=20.0, traps=[1, 2], owner_user_id=1)
    detail_field = SimpleNamespace(
        id="field-1",
        name="F1",
        area_m2=10.0,
        owner_user_id=1,
        polygon_geojson='[{"lat": 52.0, "lng": 5.0}, {"lat": 52.1, "lng": 5.1}]',
        traps=[SimpleNamespace(id="t", code="R01-P01", custom_name=None, latitude=52.0, longitude=5.0, row_index=1, position_index=1)],
    )
    db_list = FakeDB([FakeQuery(all_value=[f1, f2])])
    rows = map_api.list_field_maps(db=db_list, current_user=DummyUser(id=1, role="admin"))
    assert len(rows) == 2
    assert rows[1].trap_count == 2

    db_get = FakeDB([FakeQuery(first_value=detail_field)])
    got = map_api.get_field_map("field-1", db=db_get, current_user=DummyUser(id=1, role="admin"))
    assert got.id == "field-1"

