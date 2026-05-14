from __future__ import annotations

from decimal import Decimal
import re
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import or_, select

from app.core.config import Settings
from app.core.security import (
    TokenDecodeError,
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.enums import MerchantAuditStatus, UserRole, UserStatus, WalletStatus


_USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]{3,63}$")


def _normalized(value: Any) -> Any:
    return getattr(value, "value", value)


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_email(value: str | None) -> str | None:
    text = _clean_optional(value)
    return text.lower() if text else None


def get_user_by_username(db: Any, username: str, *, role: UserRole | None = None) -> Any | None:
    from app.models.user import UserAccount

    statement = select(UserAccount).where(UserAccount.username == username)
    if role is not None:
        statement = statement.where(UserAccount.role == role)
    users = db.execute(statement.limit(2)).scalars().all()
    if len(users) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username is ambiguous without a role.",
        )
    return users[0] if users else None


def get_user_by_id(db: Any, user_id: int) -> Any | None:
    from app.models.user import UserAccount

    statement = select(UserAccount).where(UserAccount.id == user_id)
    return db.execute(statement).scalar_one_or_none()


def _ensure_role_fields_available(
    db: Any,
    *,
    role: UserRole,
    username: str,
    phone: str | None = None,
    email: str | None = None,
) -> None:
    from app.models.user import UserAccount

    conditions = [UserAccount.username == username]
    if phone:
        conditions.append(UserAccount.phone == phone)
    if email:
        conditions.append(UserAccount.email == email.lower())

    existing = db.execute(
        select(UserAccount.id)
        .where(UserAccount.role == role)
        .where(or_(*conditions))
        .limit(1)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username, phone, or email already exists for this role.",
        )


def _password_hash(payload: Any, settings: Settings) -> str:
    return hash_password(
        payload.password,
        time_cost=settings.argon2_time_cost,
        memory_cost=settings.argon2_memory_cost,
        parallelism=settings.argon2_parallelism,
        hash_len=settings.argon2_hash_len,
        salt_len=settings.argon2_salt_len,
    )


def _ensure_jwt_secret(settings: Settings) -> None:
    if not settings.jwt_secret_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT secret key is not configured.",
        )


def _add_wallet(db: Any, user_id: int) -> None:
    from app.models.wallet import WalletAccount

    db.add(
        WalletAccount(
            user_id=user_id,
            available_balance=Decimal("0.00"),
            frozen_balance=Decimal("0.00"),
            version=0,
            status=WalletStatus.ACTIVE,
        )
    )


def register_buyer(db: Any, payload: Any, settings: Settings) -> Any:
    from app.models.order import Cart
    from app.models.user import UserAccount

    phone = _clean_optional(payload.phone)
    email = _clean_email(payload.email)
    _ensure_role_fields_available(
        db,
        role=UserRole.BUYER,
        username=payload.username,
        phone=phone,
        email=email,
    )

    user = UserAccount(
        username=payload.username,
        password_hash=_password_hash(payload, settings),
        role=UserRole.BUYER,
        status=UserStatus.ACTIVE,
        nickname=_clean_optional(payload.nickname),
        avatar_url=None,
        phone=phone,
        email=email,
    )
    db.add(user)
    db.flush()
    _add_wallet(db, user.id)
    db.add(Cart(buyer_id=user.id))
    db.flush()
    return user


def register_seller(db: Any, payload: Any, settings: Settings) -> Any:
    from app.models.user import MerchantProfile, UserAccount

    phone = _clean_optional(payload.phone)
    email = _clean_email(payload.email)
    _ensure_role_fields_available(
        db,
        role=UserRole.SELLER,
        username=payload.username,
        phone=phone,
        email=email,
    )

    user = UserAccount(
        username=payload.username,
        password_hash=_password_hash(payload, settings),
        role=UserRole.SELLER,
        status=UserStatus.ACTIVE,
        nickname=None,
        avatar_url=None,
        phone=phone,
        email=email,
    )
    db.add(user)
    db.flush()
    _add_wallet(db, user.id)
    db.add(
        MerchantProfile(
            user=user,
            shop_name=payload.shop_name,
            shop_logo_url=None,
            shop_description=_clean_optional(payload.shop_description),
            contact_name=payload.contact_name,
            contact_phone=phone or payload.phone,
            audit_material_text=None,
            audit_images_json=[],
            audit_status=MerchantAuditStatus.DRAFT,
            audit_reason=None,
        )
    )
    db.flush()
    return user


def _find_login_user(
    db: Any,
    *,
    role: UserRole,
    identifier: str,
    username_only: bool,
) -> Any | None:
    from app.models.user import UserAccount

    identifier = identifier.strip()
    if username_only:
        statement = (
            select(UserAccount)
            .where(UserAccount.role == role)
            .where(UserAccount.username == identifier)
        )
    elif "@" in identifier:
        statement = (
            select(UserAccount)
            .where(UserAccount.role == role)
            .where(UserAccount.email == identifier.lower())
        )
    elif _USERNAME_RE.fullmatch(identifier):
        statement = (
            select(UserAccount)
            .where(UserAccount.role == role)
            .where(UserAccount.username == identifier)
        )
    else:
        statement = (
            select(UserAccount)
            .where(UserAccount.role == role)
            .where(UserAccount.phone == identifier)
        )
    users = db.execute(statement).scalars().all()
    if len(users) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Login identifier is ambiguous for this role.",
        )
    return users[0] if users else None


def authenticate_user(
    db: Any,
    *,
    role: UserRole,
    identifier: str,
    password: str,
    username_only: bool = False,
) -> Any:
    user = _find_login_user(
        db,
        role=role,
        identifier=identifier,
        username_only=username_only,
    )
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    if _normalized(user.status) != UserStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled.",
        )

    return user


def build_access_token(user: Any, settings: Settings) -> tuple[str, int]:
    _ensure_jwt_secret(settings)
    token = create_access_token(
        subject=str(user.id),
        role=_normalized(user.role),
        secret_key=settings.jwt_secret_key,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        expires_minutes=settings.access_token_expire_minutes,
        extra_claims={
            "username": user.username,
        },
    )
    return token, settings.access_token_expire_minutes * 60


def _mask_contact(method: Any, value: str) -> str:
    if _normalized(method) == "email":
        name, _, domain = value.partition("@")
        if not domain:
            return "****"
        return f"{name[:2]}****@{domain}"
    if len(value) <= 7:
        return f"{value[:2]}****"
    return f"{value[:3]}****{value[-4:]}"


def _password_hash_from_plain(password: str, settings: Settings) -> str:
    class _Payload:
        pass

    payload = _Payload()
    payload.password = password
    return _password_hash(payload, settings)


def request_password_reset_token(db: Any, payload: Any, settings: Settings) -> dict[str, Any]:
    from app.models.user import UserAccount

    role = payload.role
    if role not in {UserRole.BUYER, UserRole.SELLER}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset only supports buyer and seller accounts.",
        )

    field = UserAccount.email if _normalized(payload.method) == "email" else UserAccount.phone
    user = db.execute(
        select(UserAccount)
        .where(UserAccount.role == role)
        .where(field == payload.identifier)
        .limit(1)
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if _normalized(user.status) != UserStatus.ACTIVE.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled.")

    _ensure_jwt_secret(settings)
    expires_minutes = settings.password_reset_token_expire_minutes
    token = create_access_token(
        subject=str(user.id),
        role=_normalized(user.role),
        secret_key=settings.jwt_secret_key,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        expires_minutes=expires_minutes,
        token_type="password_reset",
        extra_claims={
            "method": _normalized(payload.method),
        },
    )
    return {
        "reset_token": token,
        "expires_in": expires_minutes * 60,
        "masked_target": _mask_contact(payload.method, payload.identifier),
    }


def reset_password_with_token(db: Any, payload: Any, settings: Settings) -> None:
    from app.models.user import UserAccount

    _ensure_jwt_secret(settings)
    try:
        token_payload = decode_token(
            payload.reset_token,
            secret_key=settings.jwt_secret_key,
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        )
    except TokenDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset token.") from exc

    if token_payload.get("typ") != "password_reset":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset token.")
    role = token_payload.get("role")
    if role not in {UserRole.BUYER.value, UserRole.SELLER.value}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset token.")

    try:
        user_id = int(token_payload.get("sub", "0"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset token.") from exc

    user = db.execute(
        select(UserAccount)
        .where(UserAccount.id == user_id)
        .where(UserAccount.role == UserRole(role))
        .limit(1)
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if _normalized(user.status) != UserStatus.ACTIVE.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled.")

    user.password_hash = _password_hash_from_plain(payload.new_password, settings)
    db.flush()
