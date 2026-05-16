from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.cache import TokenBlocklistStore, get_token_blocklist_store
from app.core.config import Settings, get_settings
from app.core.security import TokenDecodeError, decode_token
from app.db.session import get_db
from app.models.enums import UserRole, UserStatus


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/buyer/login")
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/buyer/login", auto_error=False)


def get_current_token_payload(
    token: str = Depends(oauth2_scheme),
    settings: Settings = Depends(get_settings),
    token_store: TokenBlocklistStore = Depends(get_token_blocklist_store),
) -> dict[str, Any]:
    if not settings.jwt_secret_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT secret key is not configured.",
        )

    try:
        payload = decode_token(
            token,
            secret_key=settings.jwt_secret_key,
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        )
    except TokenDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if payload.get("typ") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    jti = payload.get("jti")
    if jti:
        try:
            revoked = token_store.is_revoked(str(jti))
        except Exception as exc:  # pragma: no cover - runtime connectivity branch
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Token blocklist service is unavailable.",
            ) from exc
        if revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    return payload


def get_current_user(
    payload: dict[str, Any] = Depends(get_current_token_payload),
    db: Any = Depends(get_db),
) -> Any:
    from app.services.auth.service import get_user_by_id

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token subject is missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_user_by_id(db, int(user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if getattr(user.status, "value", user.status) != UserStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active.",
        )

    return user


def get_optional_current_user(
    token: str | None = Depends(optional_oauth2_scheme),
    settings: Settings = Depends(get_settings),
    token_store: TokenBlocklistStore = Depends(get_token_blocklist_store),
    db: Any = Depends(get_db),
) -> Any | None:
    if not token or not settings.jwt_secret_key:
        return None
    try:
        payload = decode_token(
            token,
            secret_key=settings.jwt_secret_key,
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        )
    except TokenDecodeError:
        return None
    if payload.get("typ") != "access":
        return None
    jti = payload.get("jti")
    if jti:
        try:
            if token_store.is_revoked(str(jti)):
                return None
        except Exception:
            return None
    user_id = payload.get("sub")
    if user_id is None:
        return None

    from app.services.auth.service import get_user_by_id

    user = get_user_by_id(db, int(user_id))
    if user is None:
        return None
    if getattr(user.status, "value", user.status) != UserStatus.ACTIVE.value:
        return None
    return user


def require_roles(*allowed_roles: UserRole) -> Callable[[Any], Any]:
    allowed_values = {role.value for role in allowed_roles}

    def role_checker(current_user: Any = Depends(get_current_user)) -> Any:
        current_role = getattr(current_user.role, "value", current_user.role)
        if current_role not in allowed_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role permissions.",
            )
        return current_user

    return role_checker


def token_remaining_seconds(payload: dict[str, Any]) -> int:
    exp = int(payload.get("exp", 0))
    now = int(datetime.now(UTC).timestamp())
    return max(1, exp - now)
