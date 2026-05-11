from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.api import map as map_api
from app.services import graph_service as gs


def test_reassign_trap_codes_uses_assignments(monkeypatch) -> None:  # noqa: ANN001
    traps = [
        SimpleNamespace(id="t1", latitude=52.0, longitude=5.0, row_index=0, position_index=0, code="PENDING"),
        SimpleNamespace(id="t2", latitude=52.1, longitude=5.1, row_index=0, position_index=0, code="PENDING"),
    ]

    monkeypatch.setattr(
        map_api,
        "assign_grid_codes",
        lambda points: [(points[0][0], 1, 1, "R01-P01"), (points[1][0], 1, 2, "R01-P02")],
    )
    map_api._reassign_trap_codes(traps)
    assert traps[0].code == "R01-P01"
    assert traps[1].position_index == 2


def test_to_field_detail_sorts_traps_and_prefers_custom_name() -> None:
    field = SimpleNamespace(
        id="field-1",
        name="Field",
        area_m2=123.0,
        polygon_geojson='[{"lat": 52.0, "lng": 5.0}, {"lat": 52.1, "lng": 5.1}]',
    )
    traps = [
        SimpleNamespace(
            id="t2", code="R02-P01", custom_name=None, latitude=52.2, longitude=5.2, row_index=2, position_index=1
        ),
        SimpleNamespace(
            id="t1",
            code="R01-P01",
            custom_name="Trap A",
            latitude=52.0,
            longitude=5.0,
            row_index=1,
            position_index=1,
        ),
    ]

    detail = map_api._to_field_detail(field, traps)
    assert detail.traps[0].id == "t1"
    assert detail.traps[0].name == "Trap A"
    assert detail.traps[1].name == "R02-P01"


class _FakeSessionCtx:
    def __init__(self, collector: list[tuple[str, dict]]) -> None:
        self.collector = collector

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        return False

    def run(self, query: str, **params):
        self.collector.append((query, params))
        if "ORDER BY f.name ASC" in query:
            return [{"id": "f-1", "name": "Field 1", "location": "NL", "owner_user_id": 1}]
        if "RETURN f.id AS id" in query:
            return SimpleNamespace(
                single=lambda: {
                    "id": params["field_id"],
                    "name": params["name"],
                    "location": params["location"],
                    "owner_user_id": params["user_id"],
                }
            )
        return SimpleNamespace(single=lambda: None)


class _FakeDriver:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.closed = False

    def verify_connectivity(self) -> None:
        return None

    def session(self):
        return _FakeSessionCtx(self.calls)

    def close(self) -> None:
        self.closed = True


def test_graph_service_happy_path(monkeypatch) -> None:  # noqa: ANN001
    fake_driver = _FakeDriver()
    monkeypatch.setattr(gs, "get_settings", lambda: SimpleNamespace(neo4j_uri="bolt://x", neo4j_user="u", neo4j_password="p"))
    monkeypatch.setattr(gs.GraphDatabase, "driver", lambda *args, **kwargs: fake_driver)

    service = gs.GraphService()
    service.initialize()
    service.ensure_user_node(1, "u@example.com", "U")
    created = service.create_field(1, "f-1", "Field 1", "NL")
    listed = service.list_fields_for_user(1, is_admin=False)
    service.link_upload_to_field("f-1", 99, date(2026, 4, 1), 8)
    service.close()

    assert created["id"] == "f-1"
    assert listed[0]["id"] == "f-1"
    assert any("HAS_UPLOAD" in q for q, _ in fake_driver.calls)
    assert fake_driver.closed is True
