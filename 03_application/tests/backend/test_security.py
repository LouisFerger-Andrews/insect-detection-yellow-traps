from __future__ import annotations

import pytest

pytest.importorskip("jose")
pytest.importorskip("passlib")

from jose import jwt
from passlib.exc import MissingBackendError

from app.core import config as cfg
from app.core.security import ALGORITHM, create_access_token, hash_password, verify_password


def _seed_env(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("SECRET_KEY", "test-secret")
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
    payload = jwt.decode(token, "test-secret", algorithms=[ALGORITHM])
    assert payload["sub"] == "user@example.com"
    assert payload["role"] == "admin"
    assert "exp" in payload
