from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

pytest.importorskip("jose")
pytest.importorskip("passlib")

from jose import jwt
from passlib.exc import MissingBackendError
from fastapi import Response

from app.core import config as cfg
from app.core.security import ALGORITHM, create_access_token, hash_password, verify_password
from app.core.security_headers import add_security_headers


def _seed_env(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-local-tests-32")
    monkeypatch.setenv("POSTGRES_URL", "sqlite:///./test.db")
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv("NEO4J_USER", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "password")
    monkeypatch.setenv("MODEL_WEIGHTS_PATH", "weights/mock.pt")
    cfg.get_settings.cache_clear()


def test_hash_and_verify_password(monkeypatch) -> None:  # noqa: ANN001
    _seed_env(monkeypatch)
    try:
        hashed = hash_password("MyP@ssw0rd")
    except (MissingBackendError, ValueError):
        pytest.skip("bcrypt backend unavailable/incompatible in current environment")
    assert hashed != "MyP@ssw0rd"
    assert verify_password("MyP@ssw0rd", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_create_access_token_contains_expected_claims(monkeypatch) -> None:  # noqa: ANN001
    _seed_env(monkeypatch)
    token = create_access_token(subject="user@example.com", role="admin")
    payload = jwt.decode(token, "test-secret-key-for-local-tests-32", algorithms=[ALGORITHM])
    assert payload["sub"] == "user@example.com"
    assert payload["role"] == "admin"
    assert payload["type"] == "access"
    assert "iat" in payload
    assert "exp" in payload


def test_security_headers_are_added_to_responses() -> None:
    async def call_next(request):  # noqa: ANN001
        _ = request
        return Response()

    request = SimpleNamespace(url=SimpleNamespace(scheme="http"))
    response = asyncio.run(add_security_headers(request, call_next))
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"
