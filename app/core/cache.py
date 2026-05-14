from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from threading import RLock
from typing import Protocol

from app.core.config import get_settings


class TokenBlocklistStore(Protocol):
    def revoke(self, jti: str, ttl_seconds: int) -> None: ...

    def is_revoked(self, jti: str) -> bool: ...


@dataclass
class _TokenBlocklistEntry:
    expires_at: datetime


class InMemoryTokenBlocklistStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._items: dict[str, _TokenBlocklistEntry] = {}

    def revoke(self, jti: str, ttl_seconds: int) -> None:
        with self._lock:
            self._items[jti] = _TokenBlocklistEntry(
                expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds)
            )

    def is_revoked(self, jti: str) -> bool:
        with self._lock:
            entry = self._items.get(jti)
            if entry is None:
                return False
            if entry.expires_at <= datetime.now(UTC):
                self._items.pop(jti, None)
                return False
            return True


class RedisTokenBlocklistStore:
    def __init__(self, redis_url: str) -> None:
        try:
            import redis  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency branch
            raise RuntimeError("redis package is not installed.") from exc

        self._client = redis.Redis.from_url(redis_url, decode_responses=True)
        self._prefix = "seasona:auth:blacklist:"

    def revoke(self, jti: str, ttl_seconds: int) -> None:
        self._client.setex(f"{self._prefix}{jti}", ttl_seconds, "1")

    def is_revoked(self, jti: str) -> bool:
        return bool(self._client.get(f"{self._prefix}{jti}"))


@lru_cache
def get_token_blocklist_store() -> TokenBlocklistStore:
    settings = get_settings()
    if settings.redis_url:
        return RedisTokenBlocklistStore(settings.redis_url)
    if settings.environment.lower() not in {"local", "test", "development", "dev"}:
        raise RuntimeError("SEASONA_REDIS_URL is required outside local development.")
    return InMemoryTokenBlocklistStore()
