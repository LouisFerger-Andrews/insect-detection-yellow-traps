from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.api import fields as fields_api
from app.main import health


@dataclass
class DummyUser:
    id: int
    role: str = "user"


def test_create_and_list_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeGraph:
        def create_field(self, owner_user_id, field_id, name, location):  # noqa: ANN001
            return {
                "id": field_id,
                "owner_user_id": owner_user_id,
                "name": name,
                "location": location,
                "trap_count": 0,
            }

        def list_fields_for_user(self, user_id, is_admin=False):  # noqa: ANN001
            return [
                {
                    "id": "field-1",
                    "owner_user_id": user_id,
                    "name": "Field",
                    "location": "Loc",
                    "trap_count": 2,
                }
            ]

        def close(self):
            return None

    monkeypatch.setattr(fields_api, "GraphService", lambda: FakeGraph())

    payload = fields_api.FieldCreateRequest(name="Field", location="Loc")
    created = fields_api.create_field(payload, current_user=DummyUser(id=7))
    assert created.id.startswith("field-")
    assert created.owner_user_id == 7

    listed = fields_api.list_fields(current_user=DummyUser(id=7, role="admin"))
    assert len(listed) == 1
    assert listed[0].id == "field-1"


def test_health_endpoint() -> None:
    assert health() == {"status": "ok"}
