from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import admin as admin_api
from app.api import auth as auth_api
from app.api import deps as deps_api


@dataclass
class DummyUser:
    id: int
    email: str
    full_name: str
    password_hash: str
    role: str = "user"
    is_active: bool = True
    created_at: str = "2026-01-01"


class FakeQuery:
    def __init__(self, first_value=None, all_value=None, count_value=0):
        self._first = first_value
        self._all = all_value or []
        self._count = count_value

    def filter(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self

    def first(self):
        return self._first

    def order_by(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self

    def all(self):
        return self._all

    def limit(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self

    def count(self):
        return self._count


class FakeDB:
    def __init__(self, queries):
        self._queries = list(queries)
        self.added = []

    def query(self, *args, **kwargs):  # noqa: ANN002, ANN003
        if not self._queries:
            return FakeQuery()
        return self._queries.pop(0)

    def add(self, obj):  # noqa: ANN001
        self.added.append(obj)

    def commit(self):
        return None

    def refresh(self, obj):  # noqa: ANN001
        return None


def test_register_success_and_duplicate(monkeypatch: pytest.MonkeyPatch) -> None:
    user_payload = auth_api.RegisterRequest(email="u@example.com", full_name="User", password="password123")

    class FakeGraph:
        def ensure_user_node(self, *args, **kwargs):  # noqa: ANN002, ANN003
            return None

        def close(self):
            return None

    monkeypatch.setattr(auth_api, "GraphService", lambda: FakeGraph())
    monkeypatch.setattr(auth_api, "hash_password", lambda p: "hashed")

    db_ok = FakeDB([FakeQuery(first_value=None)])
    profile = auth_api.register(user_payload, db_ok)
    assert profile.email == "u@example.com"

    db_dup = FakeDB([FakeQuery(first_value=DummyUser(1, "u@example.com", "U", "x"))])
    with pytest.raises(HTTPException) as exc:
        auth_api.register(user_payload, db_dup)
    assert exc.value.status_code == 400


def test_login_and_me(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = auth_api.LoginRequest(email="u@example.com", password="password123")
    user = DummyUser(7, "u@example.com", "U", "hashed", role="admin")

    db_ok = FakeDB([FakeQuery(first_value=user)])
    monkeypatch.setattr(auth_api, "verify_password", lambda p, h: True)
    monkeypatch.setattr(auth_api, "create_access_token", lambda subject, role: f"token-{subject}-{role}")

    token = auth_api.login(payload, db_ok)
    assert token.access_token == "token-7-admin"

    db_bad = FakeDB([FakeQuery(first_value=user)])
    monkeypatch.setattr(auth_api, "verify_password", lambda p, h: False)
    with pytest.raises(HTTPException) as exc:
        auth_api.login(payload, db_bad)
    assert exc.value.status_code == 401

    assert auth_api.me(user).email == "u@example.com"


def test_get_current_user_and_require_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    user = DummyUser(9, "a@example.com", "A", "h", role="admin")
    db_ok = FakeDB([FakeQuery(first_value=user)])

    monkeypatch.setattr(deps_api, "get_settings", lambda: SimpleNamespace(secret_key="secret"))
    monkeypatch.setattr(deps_api.jwt, "decode", lambda token, key, algorithms: {"sub": "9"})

    current = deps_api.get_current_user(db=db_ok, token="tok")
    assert current.id == 9
    assert deps_api.require_admin(current_user=current).role == "admin"

    with pytest.raises(HTTPException) as exc:
        deps_api.require_admin(current_user=DummyUser(1, "u@x", "u", "h", role="user"))
    assert exc.value.status_code == 403

    db_none = FakeDB([FakeQuery(first_value=None)])
    with pytest.raises(HTTPException) as exc2:
        deps_api.get_current_user(db=db_none, token="tok")
    assert exc2.value.status_code == 401


def test_admin_overview() -> None:
    users = [DummyUser(1, "u@example.com", "U", "h")]
    uploads = [SimpleNamespace(id="1", user_id=1, field_id="f", trap_id="t", trap_code="T1", capture_date="2026-01-01", detection_count=3, confidence_avg=0.7, created_at="2026-01-01")]
    db = FakeDB([
        FakeQuery(all_value=users),
        FakeQuery(all_value=uploads),
        FakeQuery(count_value=11),
    ])

    out = admin_api.admin_overview(db=db, admin_user=DummyUser(99, "a@x", "A", "h", role="admin"))
    assert out["totals"]["users"] == 1
    assert out["totals"]["uploads"] == 1
    assert out["totals"]["detections"] == 11
