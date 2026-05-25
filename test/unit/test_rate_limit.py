from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.core.rate_limit import (
    RATE_LIMIT_PREFIX,
    RateLimitRule,
    auth_identifier_subject,
    consume_rate_limit,
    enforce_auth_rate_limit,
)
from app.models.enums import UserRole


pytestmark = pytest.mark.unit


class FakeRedis:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.values: dict[str, int] = {}
        self.expires: dict[str, int] = {}

    def incr(self, key: str) -> int:
        if self.fail:
            raise RuntimeError("redis unavailable")
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    def expire(self, key: str, seconds: int) -> None:
        self.expires[key] = seconds

    def ttl(self, key: str) -> int:
        return self.expires.get(key, -1)


def _request(ip_address: str = "127.0.0.1"):
    return SimpleNamespace(headers={}, client=SimpleNamespace(host=ip_address))


def test_consume_rate_limit_allows_until_limit_then_blocks() -> None:
    client = FakeRedis()
    rule = RateLimitRule(subject="unit:subject", limit=2, window_seconds=10)

    assert consume_rate_limit(client, rule)
    assert consume_rate_limit(client, rule)
    assert not consume_rate_limit(client, rule)
    assert client.expires[f"{RATE_LIMIT_PREFIX}unit:subject"] == 10


def test_auth_rate_limit_applies_ip_and_identifier_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeRedis()
    monkeypatch.setattr("app.core.rate_limit.get_redis_client", lambda: client)
    settings = Settings(
        redis_url="redis://unit-test",
        auth_rate_limit_window_seconds=10,
        auth_login_ip_limit=2,
        auth_login_identifier_limit=1,
    )

    enforce_auth_rate_limit(
        _request(),
        settings,
        scope="login:buyer",
        ip_limit=settings.auth_login_ip_limit,
        identifier_limit=settings.auth_login_identifier_limit,
        role=UserRole.BUYER,
        identifier="buyer@example.com",
    )

    with pytest.raises(HTTPException) as exc_info:
        enforce_auth_rate_limit(
            _request(),
            settings,
            scope="login:buyer",
            ip_limit=settings.auth_login_ip_limit,
            identifier_limit=settings.auth_login_identifier_limit,
            role=UserRole.BUYER,
            identifier="buyer@example.com",
        )

    assert exc_info.value.status_code == 429


def test_auth_rate_limit_fails_open_when_redis_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable():
        raise RuntimeError("redis unavailable")

    monkeypatch.setattr("app.core.rate_limit.get_redis_client", unavailable)
    settings = Settings(redis_url="redis://unit-test", auth_login_ip_limit=1)

    enforce_auth_rate_limit(
        _request(),
        settings,
        scope="login:buyer",
        ip_limit=1,
        identifier_limit=1,
        role=UserRole.BUYER,
        identifier="buyer@example.com",
    )


def test_auth_identifier_subject_hashes_sensitive_values() -> None:
    first = auth_identifier_subject("login", UserRole.BUYER, " Buyer@Example.COM ")
    second = auth_identifier_subject("login", UserRole.BUYER, "buyer@example.com")

    assert first == second
    assert "buyer@example.com" not in first
    assert "Buyer@Example.COM" not in first
