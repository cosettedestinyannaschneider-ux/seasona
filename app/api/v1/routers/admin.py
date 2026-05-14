from typing import Any

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import require_roles
from app.db.session import get_db
from app.models.enums import (
    DisputeStatus,
    MerchantAuditStatus,
    ProductStatus,
    RefundStatus,
    UserRole,
    UserStatus,
)
from app.schemas.dispute import DisputeDecision, DisputeListResponse, DisputePublic
from app.schemas.merchant import MerchantAuditDecision, MerchantListResponse, MerchantProfileAdmin
from app.schemas.product import (
    CategoryCreate,
    CategoryNode,
    CategoryPublic,
    CategoryUpdate,
    ProductDetail,
    ProductListResponse,
    ProductReviewDecision,
)
from app.schemas.refund import RefundDecision, RefundListResponse, RefundPublic
from app.schemas.search import SearchReindexResponse
from app.schemas.user import AdminUserListResponse, AdminUserPublic

router = APIRouter()


@router.get("/dashboard")
def admin_dashboard(
    current_admin: Any = Depends(require_roles(UserRole.ADMIN)),
    db: Any = Depends(get_db),
) -> dict[str, int]:
    from sqlalchemy import func, select

    from app.models.order import RefundApplication, RefundDispute
    from app.models.product import ProductSpu
    from app.models.user import MerchantProfile, UserAccount
    from app.services.commerce.service import escalate_overdue_refunds

    try:
        escalate_overdue_refunds(db, current_admin)
        db.commit()
        return {
            "users": db.execute(select(func.count(UserAccount.id))).scalar_one(),
            "pending_merchants": db.execute(
                select(func.count(MerchantProfile.id)).where(
                    MerchantProfile.audit_status == MerchantAuditStatus.PENDING
                )
            ).scalar_one(),
            "pending_products": db.execute(
                select(func.count(ProductSpu.id)).where(
                    ProductSpu.status == ProductStatus.PENDING_REVIEW
                )
            ).scalar_one(),
            "pending_refunds": db.execute(
                select(func.count(RefundApplication.id)).where(
                    RefundApplication.status == RefundStatus.PENDING
                )
            ).scalar_one(),
            "pending_disputes": db.execute(
                select(func.count(RefundDispute.id)).where(
                    RefundDispute.status == DisputeStatus.PENDING
                )
            ).scalar_one(),
        }
    except Exception:
        db.rollback()
        raise


@router.get("/users", response_model=AdminUserListResponse)
def list_users(
    status_filter: UserStatus | None = None,
    role_filter: UserRole | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_admin: Any = Depends(require_roles(UserRole.ADMIN)),
    db: Any = Depends(get_db),
) -> AdminUserListResponse:
    from app.services.admin.service import list_users as list_user_accounts

    items, total = list_user_accounts(
        db,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        role_filter=role_filter,
    )
    return AdminUserListResponse(
        items=[AdminUserPublic.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/users/{user_id}/disable", response_model=AdminUserPublic)
def disable_user(
    user_id: int,
    current_admin: Any = Depends(require_roles(UserRole.ADMIN)),
    db: Any = Depends(get_db),
) -> AdminUserPublic:
    from app.services.admin.service import set_user_status

    try:
        user = set_user_status(db, current_admin, user_id, target_status=UserStatus.DISABLED)
        db.commit()
        db.refresh(user)
        _ = user.merchant_profile
        return AdminUserPublic.model_validate(user)
    except Exception:
        db.rollback()
        raise


@router.post("/users/{user_id}/enable", response_model=AdminUserPublic)
def enable_user(
    user_id: int,
    current_admin: Any = Depends(require_roles(UserRole.ADMIN)),
    db: Any = Depends(get_db),
) -> AdminUserPublic:
    from app.services.admin.service import set_user_status

    try:
        user = set_user_status(db, current_admin, user_id, target_status=UserStatus.ACTIVE)
        db.commit()
        db.refresh(user)
        _ = user.merchant_profile
        return AdminUserPublic.model_validate(user)
    except Exception:
        db.rollback()
        raise


@router.post("/search/reindex", response_model=SearchReindexResponse)
def rebuild_search_documents(
    current_admin: Any = Depends(require_roles(UserRole.ADMIN)),
    db: Any = Depends(get_db),
) -> SearchReindexResponse:
    from app.services.search.service import rebuild_search_index

    index_name, total, indexed, task_uids = rebuild_search_index(db)
    return SearchReindexResponse(
        index_name=index_name,
        total=total,
        indexed=indexed,
        task_uids=task_uids,
    )


@router.get("/merchants", response_model=MerchantListResponse)
def list_merchants(
    status_filter: MerchantAuditStatus | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_admin: Any = Depends(require_roles(UserRole.ADMIN)),
    db: Any = Depends(get_db),
) -> MerchantListResponse:
    from app.services.admin.service import list_merchant_profiles

    items, total = list_merchant_profiles(
        db,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
    )
    return MerchantListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/merchants/{merchant_id}/approve", response_model=MerchantProfileAdmin)
def approve_merchant(
    merchant_id: int,
    payload: MerchantAuditDecision | None = None,
    current_admin: Any = Depends(require_roles(UserRole.ADMIN)),
    db: Any = Depends(get_db),
) -> MerchantProfileAdmin:
    from app.services.admin.service import review_merchant

    try:
        merchant = review_merchant(
            db,
            current_admin,
            merchant_id,
            approved=True,
            reason=payload.reason if payload else None,
        )
        db.commit()
        db.refresh(merchant)
        return MerchantProfileAdmin.model_validate(merchant)
    except Exception:
        db.rollback()
        raise


@router.post("/merchants/{merchant_id}/reject", response_model=MerchantProfileAdmin)
def reject_merchant(
    merchant_id: int,
    payload: MerchantAuditDecision,
    current_admin: Any = Depends(require_roles(UserRole.ADMIN)),
    db: Any = Depends(get_db),
) -> MerchantProfileAdmin:
    from app.services.admin.service import review_merchant

    try:
        merchant = review_merchant(
            db,
            current_admin,
            merchant_id,
            approved=False,
            reason=payload.reason,
        )
        db.commit()
        db.refresh(merchant)
        return MerchantProfileAdmin.model_validate(merchant)
    except Exception:
        db.rollback()
        raise


@router.get("/categories", response_model=list[CategoryNode])
def list_categories(
    current_admin: Any = Depends(require_roles(UserRole.ADMIN)),
    db: Any = Depends(get_db),
) -> list[CategoryNode]:
    from app.services.catalog.service import list_category_tree

    return list_category_tree(db)


@router.post("/categories", response_model=CategoryPublic, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreate,
    current_admin: Any = Depends(require_roles(UserRole.ADMIN)),
    db: Any = Depends(get_db),
) -> CategoryPublic:
    from app.services.catalog.service import create_category

    try:
        category = create_category(db, payload)
        db.commit()
        db.refresh(category)
        return CategoryPublic.model_validate(category)
    except Exception:
        db.rollback()
        raise


@router.patch("/categories/{category_id}", response_model=CategoryPublic)
def update_category(
    category_id: int,
    payload: CategoryUpdate,
    current_admin: Any = Depends(require_roles(UserRole.ADMIN)),
    db: Any = Depends(get_db),
) -> CategoryPublic:
    from app.services.catalog.service import update_category

    try:
        category = update_category(db, category_id, payload)
        db.commit()
        db.refresh(category)
        return CategoryPublic.model_validate(category)
    except Exception:
        db.rollback()
        raise


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: int,
    current_admin: Any = Depends(require_roles(UserRole.ADMIN)),
    db: Any = Depends(get_db),
) -> None:
    from app.services.catalog.service import delete_category as remove_category

    try:
        remove_category(db, category_id)
        db.commit()
    except Exception:
        db.rollback()
        raise


@router.get("/products", response_model=ProductListResponse)
def list_products(
    status_filter: ProductStatus | None = ProductStatus.PENDING_REVIEW,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_admin: Any = Depends(require_roles(UserRole.ADMIN)),
    db: Any = Depends(get_db),
) -> ProductListResponse:
    from app.services.catalog.service import list_admin_products

    _ = current_admin
    return list_admin_products(
        db,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
    )


@router.get("/products/pending", response_model=ProductListResponse)
def list_pending_products(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_admin: Any = Depends(require_roles(UserRole.ADMIN)),
    db: Any = Depends(get_db),
) -> ProductListResponse:
    from app.services.catalog.service import list_pending_products

    return list_pending_products(db, page=page, page_size=page_size)


@router.get("/products/{spu_id}", response_model=ProductDetail)
def get_admin_product_detail(
    spu_id: int,
    current_admin: Any = Depends(require_roles(UserRole.ADMIN)),
    db: Any = Depends(get_db),
) -> ProductDetail:
    from app.services.catalog.service import get_product_detail

    _ = current_admin
    return get_product_detail(db, spu_id)


@router.post("/products/{spu_id}/approve", response_model=ProductDetail)
def approve_product(
    spu_id: int,
    payload: ProductReviewDecision | None = None,
    current_admin: Any = Depends(require_roles(UserRole.ADMIN)),
    db: Any = Depends(get_db),
) -> ProductDetail:
    from app.services.catalog.service import get_product_detail, review_product

    try:
        product = review_product(
            db,
            current_admin,
            spu_id,
            approved=True,
            reason=payload.reason if payload else None,
        )
        db.commit()
        return get_product_detail(db, product.id)
    except Exception:
        db.rollback()
        raise


@router.post("/products/{spu_id}/reject", response_model=ProductDetail)
def reject_product(
    spu_id: int,
    payload: ProductReviewDecision,
    current_admin: Any = Depends(require_roles(UserRole.ADMIN)),
    db: Any = Depends(get_db),
) -> ProductDetail:
    from app.services.catalog.service import get_product_detail, review_product

    try:
        product = review_product(
            db,
            current_admin,
            spu_id,
            approved=False,
            reason=payload.reason,
        )
        db.commit()
        return get_product_detail(db, product.id)
    except Exception:
        db.rollback()
        raise


@router.post("/products/{spu_id}/take-down", response_model=ProductDetail)
def take_down_product(
    spu_id: int,
    payload: ProductReviewDecision | None = None,
    current_admin: Any = Depends(require_roles(UserRole.ADMIN)),
    db: Any = Depends(get_db),
) -> ProductDetail:
    from app.services.catalog.service import admin_take_down_product, get_product_detail

    try:
        product = admin_take_down_product(
            db,
            current_admin,
            spu_id,
            reason=payload.reason if payload else None,
        )
        db.commit()
        return get_product_detail(db, product.id)
    except Exception:
        db.rollback()
        raise


@router.get("/refunds", response_model=RefundListResponse)
def list_refunds(
    status_filter: RefundStatus | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_admin: Any = Depends(require_roles(UserRole.ADMIN)),
    db: Any = Depends(get_db),
) -> RefundListResponse:
    from app.services.commerce.service import list_refunds

    try:
        response = list_refunds(
            db,
            current_admin,
            status_filter=status_filter,
            page=page,
            page_size=page_size,
        )
        db.commit()
        return response
    except Exception:
        db.rollback()
        raise


@router.post("/refunds/{refund_id}/approve", response_model=RefundPublic)
def approve_refund(
    refund_id: int,
    payload: RefundDecision | None = None,
    current_admin: Any = Depends(require_roles(UserRole.ADMIN)),
    db: Any = Depends(get_db),
) -> RefundPublic:
    from app.services.commerce.service import review_refund

    try:
        refund = review_refund(
            db,
            current_admin,
            refund_id,
            approved=True,
            admin_note=payload.admin_note if payload else None,
        )
        db.commit()
        return refund
    except Exception:
        db.rollback()
        raise


@router.post("/refunds/{refund_id}/reject", response_model=RefundPublic)
def reject_refund(
    refund_id: int,
    payload: RefundDecision | None = None,
    current_admin: Any = Depends(require_roles(UserRole.ADMIN)),
    db: Any = Depends(get_db),
) -> RefundPublic:
    from app.services.commerce.service import review_refund

    try:
        refund = review_refund(
            db,
            current_admin,
            refund_id,
            approved=False,
            admin_note=payload.admin_note if payload else None,
        )
        db.commit()
        return refund
    except Exception:
        db.rollback()
        raise


@router.get("/disputes", response_model=DisputeListResponse)
def list_disputes(
    status_filter: DisputeStatus | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_admin: Any = Depends(require_roles(UserRole.ADMIN)),
    db: Any = Depends(get_db),
) -> DisputeListResponse:
    from app.services.commerce.service import list_refund_disputes

    try:
        response = list_refund_disputes(
            db,
            current_admin,
            status_filter=status_filter,
            page=page,
            page_size=page_size,
        )
        db.commit()
        return response
    except Exception:
        db.rollback()
        raise


@router.post("/disputes/{dispute_id}/approve", response_model=DisputePublic)
def approve_dispute(
    dispute_id: int,
    payload: DisputeDecision | None = None,
    current_admin: Any = Depends(require_roles(UserRole.ADMIN)),
    db: Any = Depends(get_db),
) -> DisputePublic:
    from app.services.commerce.service import review_refund_dispute

    try:
        dispute = review_refund_dispute(
            db,
            current_admin,
            dispute_id=dispute_id,
            approved=True,
            resolution_note=payload.resolution_note if payload else None,
        )
        db.commit()
        return dispute
    except Exception:
        db.rollback()
        raise


@router.post("/disputes/{dispute_id}/reject", response_model=DisputePublic)
def reject_dispute(
    dispute_id: int,
    payload: DisputeDecision | None = None,
    current_admin: Any = Depends(require_roles(UserRole.ADMIN)),
    db: Any = Depends(get_db),
) -> DisputePublic:
    from app.services.commerce.service import review_refund_dispute

    try:
        dispute = review_refund_dispute(
            db,
            current_admin,
            dispute_id=dispute_id,
            approved=False,
            resolution_note=payload.resolution_note if payload else None,
        )
        db.commit()
        return dispute
    except Exception:
        db.rollback()
        raise
