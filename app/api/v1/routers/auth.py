from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.cache import TokenBlocklistStore, get_token_blocklist_store
from app.core.config import Settings, get_settings
from app.core.dependencies import (
    get_current_token_payload,
    get_current_user,
    token_remaining_seconds,
)
from app.db.session import get_db
from app.models.enums import UserRole
from app.schemas.auth import (
    AdminLoginRequest,
    AuthResponse,
    BuyerRegisterRequest,
    PasswordResetConfirmRequest,
    PasswordResetConfirmResponse,
    PasswordResetRequest,
    PasswordResetTicket,
    RoleLoginRequest,
    SellerRegisterRequest,
)
from app.schemas.user import UserContactUpdate, UserPasswordUpdate, UserProfileUpdate, UserPublic


router = APIRouter()


def _ensure_jwt_configured(settings: Settings) -> None:
    if not settings.jwt_secret_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SEASONA_JWT_SECRET_KEY is not configured.",
        )


def _auth_response(user: Any, settings: Settings) -> AuthResponse:
    from app.services.auth.service import build_access_token

    _ = user.merchant_profile
    access_token, expires_in = build_access_token(user, settings)
    return AuthResponse(access_token=access_token, expires_in=expires_in, user=user)


def _register_and_commit(
    *,
    db: Any,
    settings: Settings,
    register_func: Callable[[Any, Any, Settings], Any],
    payload: Any,
) -> AuthResponse:
    _ensure_jwt_configured(settings)
    try:
        user = register_func(db, payload, settings)
        db.commit()
        db.refresh(user)
        return _auth_response(user, settings)
    except Exception:
        db.rollback()
        raise


@router.post(
    "/buyer/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_buyer(
    payload: BuyerRegisterRequest,
    db: Any = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    from app.services.auth.service import register_buyer as create_buyer

    return _register_and_commit(
        db=db,
        settings=settings,
        register_func=create_buyer,
        payload=payload,
    )


@router.post(
    "/seller/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_seller(
    payload: SellerRegisterRequest,
    db: Any = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    from app.services.auth.service import register_seller as create_seller

    return _register_and_commit(
        db=db,
        settings=settings,
        register_func=create_seller,
        payload=payload,
    )


@router.post("/buyer/login", response_model=AuthResponse)
def login_buyer(
    payload: RoleLoginRequest,
    db: Any = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    from app.services.auth.service import authenticate_user

    _ensure_jwt_configured(settings)
    user = authenticate_user(
        db,
        role=UserRole.BUYER,
        identifier=payload.identifier,
        password=payload.password,
    )
    return _auth_response(user, settings)


@router.post("/seller/login", response_model=AuthResponse)
def login_seller(
    payload: RoleLoginRequest,
    db: Any = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    from app.services.auth.service import authenticate_user

    _ensure_jwt_configured(settings)
    user = authenticate_user(
        db,
        role=UserRole.SELLER,
        identifier=payload.identifier,
        password=payload.password,
    )
    return _auth_response(user, settings)


@router.post("/admin/login", response_model=AuthResponse)
def login_admin(
    payload: AdminLoginRequest,
    db: Any = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    from app.services.auth.service import authenticate_user

    _ensure_jwt_configured(settings)
    user = authenticate_user(
        db,
        role=UserRole.ADMIN,
        identifier=payload.username,
        password=payload.password,
        username_only=True,
    )
    return _auth_response(user, settings)


@router.get("/me", response_model=UserPublic)
def me(current_user: Any = Depends(get_current_user)) -> Any:
    return current_user


@router.patch("/me", response_model=UserPublic)
def update_me(
    payload: UserProfileUpdate,
    current_user: Any = Depends(get_current_user),
    db: Any = Depends(get_db),
) -> UserPublic:
    current_role = getattr(current_user.role, "value", current_user.role)
    if current_role == UserRole.SELLER.value and "avatar_url" in payload.model_fields_set:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seller avatar is represented by shop_logo_url. Use /seller/profile instead.",
        )

    try:
        if "nickname" in payload.model_fields_set:
            current_user.nickname = payload.nickname
        if "avatar_url" in payload.model_fields_set:
            current_user.avatar_url = payload.avatar_url
        db.commit()
        db.refresh(current_user)
        _ = current_user.merchant_profile
        return UserPublic.model_validate(current_user)
    except Exception:
        db.rollback()
        raise


@router.patch("/me/contact", response_model=UserPublic)
def update_my_contact(
    payload: UserContactUpdate,
    current_user: Any = Depends(get_current_user),
    db: Any = Depends(get_db),
) -> UserPublic:
    from sqlalchemy import or_, select
    from sqlalchemy.exc import IntegrityError

    from app.core.security import verify_password
    from app.models.enums import UserRole
    from app.models.user import UserAccount

    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    try:
        changed_fields = payload.model_fields_set - {"current_password"}
        conditions = []
        if "phone" in changed_fields and payload.phone:
            conditions.append(UserAccount.phone == payload.phone)
        if "email" in changed_fields and payload.email:
            conditions.append(UserAccount.email == payload.email)
        if conditions:
            existing = db.execute(
                select(UserAccount.id)
                .where(UserAccount.role == current_user.role)
                .where(UserAccount.id != current_user.id)
                .where(or_(*conditions))
                .limit(1)
            ).scalar_one_or_none()
            if existing is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Phone or email already exists for this role.",
                )

        old_phone = current_user.phone
        if "phone" in changed_fields:
            current_user.phone = payload.phone
            current_role = getattr(current_user.role, "value", current_user.role)
            merchant = getattr(current_user, "merchant_profile", None)
            if (
                current_role == UserRole.SELLER.value
                and merchant is not None
                and merchant.contact_phone == old_phone
                and payload.phone
            ):
                merchant.contact_phone = payload.phone
        if "email" in changed_fields:
            current_user.email = payload.email
        db.commit()
        db.refresh(current_user)
        _ = current_user.merchant_profile
        return UserPublic.model_validate(current_user)
    except HTTPException:
        db.rollback()
        raise


@router.patch("/me/password")
def update_my_password(
    payload: UserPasswordUpdate,
    current_user: Any = Depends(get_current_user),
    db: Any = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    from app.core.security import hash_password, verify_password

    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )
    if verify_password(payload.new_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password.",
        )
    try:
        current_user.password_hash = hash_password(
            payload.new_password,
            time_cost=settings.argon2_time_cost,
            memory_cost=settings.argon2_memory_cost,
            parallelism=settings.argon2_parallelism,
            hash_len=settings.argon2_hash_len,
            salt_len=settings.argon2_salt_len,
        )
        db.commit()
        return {"detail": "password updated"}
    except Exception:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phone or email already exists for this role.",
        ) from exc
    except Exception:
        db.rollback()
        raise


@router.post("/password-reset/request", response_model=PasswordResetTicket)
def request_password_reset(
    payload: PasswordResetRequest,
    db: Any = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PasswordResetTicket:
    from app.services.auth.service import request_password_reset_token

    _ensure_jwt_configured(settings)
    ticket = request_password_reset_token(db, payload, settings)
    return PasswordResetTicket(**ticket)


@router.post("/password-reset/confirm", response_model=PasswordResetConfirmResponse)
def confirm_password_reset(
    payload: PasswordResetConfirmRequest,
    db: Any = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PasswordResetConfirmResponse:
    from app.services.auth.service import reset_password_with_token

    _ensure_jwt_configured(settings)
    try:
        reset_password_with_token(db, payload, settings)
        db.commit()
        return PasswordResetConfirmResponse()
    except Exception:
        db.rollback()
        raise


@router.post("/logout")
def logout(
    payload: dict[str, Any] = Depends(get_current_token_payload),
    token_store: TokenBlocklistStore = Depends(get_token_blocklist_store),
) -> dict[str, str]:
    jti = payload.get("jti")
    if jti:
        try:
            token_store.revoke(str(jti), token_remaining_seconds(payload))
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Token blocklist service is unavailable.",
            ) from exc
    return {"detail": "logged out"}
