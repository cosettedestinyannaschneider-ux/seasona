from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.enums import MerchantAuditStatus, UserRole, UserStatus
from app.models.user import MerchantProfile, UserAccount


def _require_admin(user: Any) -> None:
    role = getattr(user.role, "value", user.role)
    if role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permission required.",
        )


def list_merchant_profiles(
    db: Any,
    *,
    page: int = 1,
    page_size: int = 20,
    status_filter: MerchantAuditStatus | None = None,
) -> tuple[list[MerchantProfile], int]:
    statement = select(MerchantProfile)
    if status_filter is not None:
        statement = statement.where(MerchantProfile.audit_status == status_filter)
    total = db.execute(select(func.count()).select_from(statement.subquery())).scalar_one()
    items = db.execute(
        statement.order_by(MerchantProfile.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    return items, total


def list_users(
    db: Any,
    *,
    page: int = 1,
    page_size: int = 20,
    status_filter: UserStatus | None = None,
    role_filter: UserRole | None = None,
) -> tuple[list[UserAccount], int]:
    statement = (
        select(UserAccount)
        .options(selectinload(UserAccount.merchant_profile))
        .where(UserAccount.role != UserRole.ADMIN)
    )
    if status_filter is not None:
        statement = statement.where(UserAccount.status == status_filter)
    if role_filter is not None:
        statement = statement.where(UserAccount.role == role_filter)
    total = db.execute(select(func.count()).select_from(statement.subquery())).scalar_one()
    items = db.execute(
        statement.order_by(UserAccount.created_at.desc(), UserAccount.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()
    return items, total


def review_merchant(
    db: Any,
    admin_user: Any,
    merchant_id: int,
    *,
    approved: bool,
    reason: str | None = None,
) -> MerchantProfile:
    _require_admin(admin_user)
    merchant = db.get(MerchantProfile, merchant_id)
    if merchant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Merchant profile not found.",
        )
    merchant_status = getattr(merchant.audit_status, "value", merchant.audit_status)
    if merchant_status != MerchantAuditStatus.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending merchant audit applications can be reviewed.",
        )
    merchant.audit_status = (
        MerchantAuditStatus.APPROVED if approved else MerchantAuditStatus.REJECTED
    )
    merchant.audit_reason = reason
    merchant.updated_at = datetime.now(UTC)
    db.flush()
    from app.services.search.service import sync_merchant_search_documents

    sync_merchant_search_documents(db, merchant.id)
    return merchant


def set_user_status(
    db: Any,
    admin_user: Any,
    user_id: int,
    *,
    target_status: UserStatus,
) -> UserAccount:
    _require_admin(admin_user)
    user = db.execute(
        select(UserAccount).options(selectinload(UserAccount.merchant_profile)).where(UserAccount.id == user_id)
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found.",
        )
    if getattr(user.role, "value", user.role) == UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin accounts cannot be managed here.",
        )
    if user.id == admin_user.id and target_status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin account cannot disable itself.",
        )
    user.status = target_status
    user.updated_at = datetime.now(UTC)
    db.flush()
    if user.merchant_profile is not None:
        from app.services.search.service import sync_merchant_search_documents

        sync_merchant_search_documents(db, user.merchant_profile.id)
    return user
