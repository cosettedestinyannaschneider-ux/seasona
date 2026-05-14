from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.low_level import Type

try:
    import jwt as pyjwt  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    pyjwt = None

_ARGON2_TIME_COST = 2
_ARGON2_MEMORY_COST = 19456
_ARGON2_PARALLELISM = 1
_ARGON2_HASH_LEN = 32
_ARGON2_SALT_LEN = 16


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _password_hasher(
    *,
    time_cost: int = _ARGON2_TIME_COST,
    memory_cost: int = _ARGON2_MEMORY_COST,
    parallelism: int = _ARGON2_PARALLELISM,
    hash_len: int = _ARGON2_HASH_LEN,
    salt_len: int = _ARGON2_SALT_LEN,
) -> PasswordHasher:
    return PasswordHasher(
        time_cost=time_cost,
        memory_cost=memory_cost,
        parallelism=parallelism,
        hash_len=hash_len,
        salt_len=salt_len,
        type=Type.ID,
    )


def hash_password(
    password: str,
    *,
    time_cost: int = _ARGON2_TIME_COST,
    memory_cost: int = _ARGON2_MEMORY_COST,
    parallelism: int = _ARGON2_PARALLELISM,
    hash_len: int = _ARGON2_HASH_LEN,
    salt_len: int = _ARGON2_SALT_LEN,
) -> str:
    return _password_hasher(
        time_cost=time_cost,
        memory_cost=memory_cost,
        parallelism=parallelism,
        hash_len=hash_len,
        salt_len=salt_len,
    ).hash(password)


def verify_password(password: str, encoded: str) -> bool:
    if not encoded.startswith("$argon2id$"):
        return False
    try:
        return bool(_password_hasher().verify(encoded, password))
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def create_jti() -> str:
    return secrets.token_urlsafe(24)


def _encode_json(data: dict[str, Any]) -> bytes:
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _signing_input(header: dict[str, Any], payload: dict[str, Any]) -> str:
    return f"{_b64url_encode(_encode_json(header))}.{_b64url_encode(_encode_json(payload))}"


def _sign_hs256(secret_key: str, signing_input: str) -> str:
    signature = hmac.new(
        secret_key.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return _b64url_encode(signature)


def create_access_token(
    *,
    subject: str,
    role: str,
    secret_key: str,
    issuer: str,
    audience: str,
    expires_minutes: int,
    token_type: str = "access",
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "typ": token_type,
        "iss": issuer,
        "aud": audience,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expires_minutes)).timestamp()),
        "jti": create_jti(),
    }
    if extra_claims:
        payload.update(extra_claims)

    if pyjwt is not None:
        return pyjwt.encode(payload, secret_key, algorithm="HS256")

    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = _signing_input(header, payload)
    signature = _sign_hs256(secret_key, signing_input)
    return f"{signing_input}.{signature}"


class TokenDecodeError(ValueError):
    pass


def decode_token(token: str, *, secret_key: str, issuer: str, audience: str) -> dict[str, Any]:
    if pyjwt is not None:
        try:
            payload = pyjwt.decode(
                token,
                secret_key,
                algorithms=["HS256"],
                issuer=issuer,
                audience=audience,
            )
        except Exception as exc:  # pragma: no cover - optional dependency branch
            raise TokenDecodeError(str(exc)) from exc
        return dict(payload)

    try:
        header_raw, payload_raw, signature_raw = token.split(".", 2)
        header = json.loads(_b64url_decode(header_raw))
        if header.get("alg") != "HS256":
            raise TokenDecodeError("Unsupported token algorithm.")
        signing_input = f"{header_raw}.{payload_raw}"
        expected_signature = _sign_hs256(secret_key, signing_input)
        if not hmac.compare_digest(expected_signature, signature_raw):
            raise TokenDecodeError("Invalid token signature.")
        payload = json.loads(_b64url_decode(payload_raw))
    except (ValueError, json.JSONDecodeError) as exc:
        raise TokenDecodeError("Malformed token.") from exc

    now = int(datetime.now(UTC).timestamp())
    if payload.get("iss") != issuer or payload.get("aud") != audience:
        raise TokenDecodeError("Invalid token audience or issuer.")
    if int(payload.get("exp", 0)) < now:
        raise TokenDecodeError("Token has expired.")
    return payload
