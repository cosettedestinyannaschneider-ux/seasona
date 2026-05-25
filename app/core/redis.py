from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.core.config import get_settings


@lru_cache
def get_redis_client() -> Any | None:
    settings = get_settings()
    if not settings.redis_url:
        return None

    try:
        import redis  # type: ignore
    except ImportError as exc:  # pragma: no cover - runtime dependency branch
        raise RuntimeError("redis package is not installed.") from exc

    return redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_timeout=settings.redis_socket_timeout_seconds,
        socket_connect_timeout=settings.redis_socket_connect_timeout_seconds,
        health_check_interval=settings.redis_health_check_interval_seconds,
    )


def get_required_redis_client() -> Any:
    client = get_redis_client()
    if client is None:
        raise RuntimeError("SEASONA_REDIS_URL is not configured.")
    return client
