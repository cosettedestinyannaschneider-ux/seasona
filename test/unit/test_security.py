from __future__ import annotations

from datetime import UTC, datetime

import pytest
from freezegun import freeze_time

from app.core.security import TokenDecodeError, create_access_token, decode_token, hash_password, verify_password


pytestmark = pytest.mark.unit


def test_password_hash_verification_uses_configurable_costs() -> None:
    encoded = hash_password("password123", time_cost=1, memory_cost=8192, parallelism=1)

    assert verify_password("password123", encoded)
    assert not verify_password("wrong-password", encoded)


def test_access_token_round_trip_contains_expected_claims() -> None:
    with freeze_time(datetime(2026, 5, 20, 8, 0, tzinfo=UTC)):
        token = create_access_token(
            subject="42",
            role="buyer",
            secret_key="secret-secret-secret-secret-secret12",
            issuer="seasona",
            audience="seasona-users",
            expires_minutes=30,
            extra_claims={"username": "buyer1"},
        )
        payload = decode_token(
            token,
            secret_key="secret-secret-secret-secret-secret12",
            issuer="seasona",
            audience="seasona-users",
        )

    assert payload["sub"] == "42"
    assert payload["role"] == "buyer"
    assert payload["typ"] == "access"
    assert payload["username"] == "buyer1"
    assert payload["exp"] - payload["iat"] == 30 * 60
    assert payload["jti"]


def test_decode_token_rejects_wrong_audience_and_expired_token() -> None:
    with freeze_time(datetime(2026, 5, 20, 8, 0, tzinfo=UTC)):
        token = create_access_token(
            subject="42",
            role="buyer",
            secret_key="secret-secret-secret-secret-secret12",
            issuer="seasona",
            audience="seasona-users",
            expires_minutes=1,
        )

    with pytest.raises(TokenDecodeError):
        decode_token(token, secret_key="secret-secret-secret-secret-secret12", issuer="seasona", audience="other")

    with freeze_time(datetime(2026, 5, 20, 8, 2, tzinfo=UTC)):
        with pytest.raises(TokenDecodeError):
            decode_token(
                token,
                secret_key="secret-secret-secret-secret-secret12",
                issuer="seasona",
                audience="seasona-users",
            )
