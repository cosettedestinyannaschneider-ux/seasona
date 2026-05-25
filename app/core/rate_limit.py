from __future__ import annotations

from dataclasses import dataclass
import hashlib
import logging
from typing import Any

from fastapi import HTTPException, Request, status

from app.core.config import Settings
from app.core.redis import get_redis_client


logger = logging.getLogger(__name__)
RATE_LIMIT_PREFIX = "seasona:rate-limit:"


class RateLimitExceeded(Exception):
    pass


@dataclass(frozen=True)
class RateLimitRule:
    subject: str
    limit: int
    window_seconds: int


def _hash_value(value: str) -> str:
    normalized = value.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def client_ip_from_request(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def auth_ip_subject(scope: str, ip_address: str) -> str:
    return f"auth:{scope}:ip:{_hash_value(ip_address)}"


def auth_identifier_subject(scope: str, role: Any, identifier: str) -> str:
    role_value = getattr(role, "value", role) or "unknown"
    return f"auth:{scope}:identifier:{role_value}:{_hash_value(identifier)}"


def consume_rate_limit(client: Any, rule: RateLimitRule) -> bool:
    if rule.limit <= 0 or rule.window_seconds <= 0:
        return True

    key = f"{RATE_LIMIT_PREFIX}{rule.subject}"
    count = int(client.incr(key))
    if count == 1:
        client.expire(key, rule.window_seconds)
    elif int(client.ttl(key)) < 0:
        client.expire(key, rule.window_seconds)
    return count <= rule.limit


def enforce_auth_rate_limit(
    request: Request,
    settings: Settings,
    *,
    scope: str,
    ip_limit: int,
    identifier_limit: int | None = None,
    role: Any | None = None,
    identifier: str | None = None,
) -> None:
    if not settings.auth_rate_limit_enabled:
        return
    if not settings.redis_url:
        return

    rules = [
        RateLimitRule(
            subject=auth_ip_subject(scope, client_ip_from_request(request)),
            limit=ip_limit,
            window_seconds=settings.auth_rate_limit_window_seconds,
        )
    ]
    if identifier and identifier_limit is not None:
        rules.append(
            RateLimitRule(
                subject=auth_identifier_subject(scope, role, identifier),
                limit=identifier_limit,
                window_seconds=settings.auth_rate_limit_window_seconds,
            )
        )

    try:
        client = get_redis_client()
        if client is None:
            return
        for rule in rules:
            if not consume_rate_limit(client, rule):
                raise RateLimitExceeded
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
        ) from exc
    except Exception:
        logger.warning("Auth rate limiter is unavailable; request is allowed.", exc_info=True)
