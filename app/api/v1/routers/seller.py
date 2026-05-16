from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import require_roles
from app.db.session import get_db
from app.models.enums import MerchantAuditStatus, OrderStatus, ProductStatus, RefundStatus, UserRole
from app.schemas.order import OrderDetail, OrderListResponse
from app.schemas.merchant import (
    MerchantAuditMaterialUpdate,
    MerchantProfileAdmin,
    MerchantProfileUpdate,
)
from app.schemas.product import (
    ProductCreate,
    ProductDetail,
    ProductListResponse,
    ProductUpdate,
)
from app.schemas.refund import RefundListResponse, RefundPublic, SellerRefundDecision
from app.schemas.review import ReviewListResponse, ReviewProductListResponse, ReviewPublic, ReviewReply
from app.schemas.wallet import SellerEarningsPublic, WalletLedgerListResponse, WalletPublic

router = APIRouter()


def _seller_merchant(current_seller: Any) -> Any:
    merchant = getattr(current_seller, "merchant_profile", None)
    if merchant is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seller profile is missing.",
        )
    return merchant


@router.get("/dashboard")
def seller_dashboard(
    current_seller: Any = Depends(require_roles(UserRole.SELLER)),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    from sqlalchemy import func, select

    from app.models.order import Order
    from app.services.commerce.service import escalate_overdue_refunds

    merchant = _seller_merchant(current_seller)
    try:
        escalate_overdue_refunds(db, current_seller)
        db.commit()
    except Exception:
        db.rollback()
        raise

    rows = db.execute(
        select(Order.status, func.count(Order.id))
        .where(Order.seller_id == merchant.id, Order.paid_at.is_not(None))
        .group_by(Order.status)
    ).all()
    return {
        "merchant_id": merchant.id,
        "shop_name": merchant.shop_name,
        "audit_status": getattr(merchant.audit_status, "value", merchant.audit_status),
        "order_counts": {
            getattr(order_status, "value", order_status): count
            for order_status, count in rows
        },
    }


@router.get("/profile", response_model=MerchantProfileAdmin)
def get_seller_profile(
    current_seller: Any = Depends(require_roles(UserRole.SELLER)),
) -> MerchantProfileAdmin:
    return MerchantProfileAdmin.model_validate(_seller_merchant(current_seller))


@router.patch("/profile", response_model=MerchantProfileAdmin)
def update_seller_profile(
    payload: MerchantProfileUpdate,
    current_seller: Any = Depends(require_roles(UserRole.SELLER)),
    db: Any = Depends(get_db),
) -> MerchantProfileAdmin:
    merchant = _seller_merchant(current_seller)
    merchant_status = getattr(merchant.audit_status, "value", merchant.audit_status)
    if merchant_status == MerchantAuditStatus.SUSPENDED.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Suspended merchant profile cannot be updated.",
        )

    try:
        if "shop_name" in payload.model_fields_set:
            merchant.shop_name = payload.shop_name
        if "shop_logo_url" in payload.model_fields_set:
            merchant.shop_logo_url = payload.shop_logo_url
        if "shop_description" in payload.model_fields_set:
            merchant.shop_description = payload.shop_description
        db.commit()
        db.refresh(merchant)
        return MerchantProfileAdmin.model_validate(merchant)
    except Exception:
        db.rollback()
        raise


@router.patch("/audit-materials", response_model=MerchantProfileAdmin)
def update_audit_materials(
    payload: MerchantAuditMaterialUpdate,
    current_seller: Any = Depends(require_roles(UserRole.SELLER)),
    db: Any = Depends(get_db),
) -> MerchantProfileAdmin:
    merchant = _seller_merchant(current_seller)
    merchant_status = getattr(merchant.audit_status, "value", merchant.audit_status)
    if merchant_status not in {
        MerchantAuditStatus.DRAFT.value,
        MerchantAuditStatus.REJECTED.value,
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audit materials can only be updated before submission or after rejection.",
        )

    try:
        if "audit_material_text" in payload.model_fields_set:
            merchant.audit_material_text = payload.audit_material_text
        if "audit_images_json" in payload.model_fields_set:
            merchant.audit_images_json = payload.audit_images_json or []
        merchant.audit_reason = None
        db.commit()
        db.refresh(merchant)
        return MerchantProfileAdmin.model_validate(merchant)
    except Exception:
        db.rollback()
        raise


@router.post("/audit-materials/submit", response_model=MerchantProfileAdmin)
def submit_audit_materials(
    current_seller: Any = Depends(require_roles(UserRole.SELLER)),
    db: Any = Depends(get_db),
) -> MerchantProfileAdmin:
    merchant = _seller_merchant(current_seller)
    merchant_status = getattr(merchant.audit_status, "value", merchant.audit_status)
    if merchant_status not in {
        MerchantAuditStatus.DRAFT.value,
        MerchantAuditStatus.REJECTED.value,
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audit can only be submitted from draft or rejected status.",
        )

    try:
        merchant.audit_status = MerchantAuditStatus.PENDING
        merchant.audit_reason = None
        db.commit()
        db.refresh(merchant)
        return MerchantProfileAdmin.model_validate(merchant)
    except Exception:
        db.rollback()
        raise


@router.get("/wallet", response_model=WalletPublic)
def get_seller_wallet(
    current_seller: Any = Depends(require_roles(UserRole.SELLER)),
    db: Any = Depends(get_db),
) -> WalletPublic:
    from app.services.commerce.service import get_seller_wallet as load_seller_wallet

    return WalletPublic.model_validate(load_seller_wallet(db, current_seller))


@router.get("/earnings", response_model=SellerEarningsPublic)
def get_seller_earnings(
    current_seller: Any = Depends(require_roles(UserRole.SELLER)),
    db: Any = Depends(get_db),
) -> SellerEarningsPublic:
    from app.services.commerce.service import get_seller_earnings as load_seller_earnings

    return load_seller_earnings(db, current_seller)


@router.get("/wallet/ledger", response_model=WalletLedgerListResponse)
def list_seller_wallet_ledger(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_seller: Any = Depends(require_roles(UserRole.SELLER)),
    db: Any = Depends(get_db),
) -> WalletLedgerListResponse:
    from app.services.commerce.service import list_wallet_ledgers

    return list_wallet_ledgers(db, current_seller, page=page, page_size=page_size)


@router.get("/products", response_model=ProductListResponse)
def list_my_products(
    status_filter: ProductStatus | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_seller: Any = Depends(require_roles(UserRole.SELLER)),
    db: Any = Depends(get_db),
) -> ProductListResponse:
    from app.services.catalog.service import list_seller_products

    return list_seller_products(
        db,
        current_seller,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
    )


@router.post(
    "/products",
    response_model=ProductDetail,
    status_code=status.HTTP_201_CREATED,
)
def create_my_product(
    payload: ProductCreate,
    current_seller: Any = Depends(require_roles(UserRole.SELLER)),
    db: Any = Depends(get_db),
) -> ProductDetail:
    from app.services.catalog.service import create_product, get_product_detail

    try:
        product = create_product(db, current_seller, payload)
        db.commit()
        return get_product_detail(db, product.id)
    except Exception:
        db.rollback()
        raise


@router.get("/products/{spu_id}", response_model=ProductDetail)
def get_my_product(
    spu_id: int,
    current_seller: Any = Depends(require_roles(UserRole.SELLER)),
    db: Any = Depends(get_db),
) -> ProductDetail:
    from fastapi import HTTPException

    from app.models.enums import MerchantAuditStatus
    from app.services.catalog.service import get_product_detail

    detail = get_product_detail(db, spu_id)
    merchant = getattr(current_seller, "merchant_profile", None)
    merchant_status = getattr(getattr(merchant, "audit_status", None), "value", getattr(merchant, "audit_status", None))
    if (
        merchant is None
        or merchant_status != MerchantAuditStatus.APPROVED.value
        or detail.merchant_id != merchant.id
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not own this product.")
    return detail


@router.patch("/products/{spu_id}", response_model=ProductDetail)
def update_my_product(
    spu_id: int,
    payload: ProductUpdate,
    current_seller: Any = Depends(require_roles(UserRole.SELLER)),
    db: Any = Depends(get_db),
) -> ProductDetail:
    from app.services.catalog.service import get_product_detail, update_product

    try:
        product = update_product(db, current_seller, spu_id, payload)
        db.commit()
        return get_product_detail(db, product.id)
    except Exception:
        db.rollback()
        raise


@router.delete("/products/{spu_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_product(
    spu_id: int,
    current_seller: Any = Depends(require_roles(UserRole.SELLER)),
    db: Any = Depends(get_db),
) -> None:
    from app.services.catalog.service import delete_seller_product

    try:
        delete_seller_product(db, current_seller, spu_id)
        db.commit()
    except Exception:
        db.rollback()
        raise


@router.patch("/skus/{sku_id}", deprecated=True)
def update_my_sku(
    sku_id: int,
    current_seller: Any = Depends(require_roles(UserRole.SELLER)),
) -> dict[str, Any]:
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail={
            "code": "seller_sku_patch_deprecated",
            "message": "This endpoint has been retired. Update product SKUs via PATCH /api/v1/seller/products/{spu_id}.",
            "sku_id": sku_id,
        },
    )


@router.post("/products/{spu_id}/submit", response_model=ProductDetail)
def submit_my_product(
    spu_id: int,
    current_seller: Any = Depends(require_roles(UserRole.SELLER)),
    db: Any = Depends(get_db),
) -> ProductDetail:
    from app.services.catalog.service import get_product_detail, submit_product_for_review

    try:
        product = submit_product_for_review(db, current_seller, spu_id)
        db.commit()
        return get_product_detail(db, product.id)
    except Exception:
        db.rollback()
        raise


@router.post("/products/{spu_id}/offline", response_model=ProductDetail)
def offline_my_product(
    spu_id: int,
    current_seller: Any = Depends(require_roles(UserRole.SELLER)),
    db: Any = Depends(get_db),
) -> ProductDetail:
    from app.services.catalog.service import get_product_detail, set_product_offline

    try:
        product = set_product_offline(db, current_seller, spu_id)
        db.commit()
        return get_product_detail(db, product.id)
    except Exception:
        db.rollback()
        raise


@router.post("/products/{spu_id}/online", response_model=ProductDetail)
def online_my_product(
    spu_id: int,
    current_seller: Any = Depends(require_roles(UserRole.SELLER)),
    db: Any = Depends(get_db),
) -> ProductDetail:
    from app.services.catalog.service import get_product_detail, set_product_online

    try:
        product = set_product_online(db, current_seller, spu_id)
        db.commit()
        return get_product_detail(db, product.id)
    except Exception:
        db.rollback()
        raise


@router.get("/orders", response_model=OrderListResponse)
def list_seller_orders(
    status_filter: OrderStatus | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_seller: Any = Depends(require_roles(UserRole.SELLER)),
    db: Any = Depends(get_db),
) -> OrderListResponse:
    from app.services.commerce.service import list_orders

    try:
        response = list_orders(
            db,
            current_seller,
            status_filter=status_filter,
            page=page,
            page_size=page_size,
        )
        db.commit()
        return response
    except Exception:
        db.rollback()
        raise


@router.get("/orders/{order_id}", response_model=OrderDetail)
def get_seller_order(
    order_id: int,
    current_seller: Any = Depends(require_roles(UserRole.SELLER)),
    db: Any = Depends(get_db),
) -> OrderDetail:
    from app.services.commerce.service import get_order_detail

    try:
        order = get_order_detail(db, current_seller, order_id)
        db.commit()
        return order
    except Exception:
        db.rollback()
        raise


@router.post("/orders/{order_id}/ship", response_model=OrderDetail)
def ship_seller_order(
    order_id: int,
    current_seller: Any = Depends(require_roles(UserRole.SELLER)),
    db: Any = Depends(get_db),
) -> OrderDetail:
    from app.services.commerce.service import ship_order

    try:
        order = ship_order(db, current_seller, order_id)
        db.commit()
        return order
    except Exception:
        db.rollback()
        raise


@router.get("/refunds", response_model=RefundListResponse)
def list_seller_refunds(
    status_filter: RefundStatus | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_seller: Any = Depends(require_roles(UserRole.SELLER)),
    db: Any = Depends(get_db),
) -> RefundListResponse:
    from app.services.commerce.service import list_refunds

    try:
        response = list_refunds(
            db,
            current_seller,
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
def approve_seller_refund(
    refund_id: int,
    payload: SellerRefundDecision | None = None,
    current_seller: Any = Depends(require_roles(UserRole.SELLER)),
    db: Any = Depends(get_db),
) -> RefundPublic:
    from app.services.commerce.service import review_seller_refund

    try:
        refund = review_seller_refund(
            db,
            current_seller,
            refund_id,
            approved=True,
            seller_note=payload.seller_note if payload else None,
        )
        db.commit()
        return refund
    except Exception:
        db.rollback()
        raise


@router.post("/refunds/{refund_id}/reject", response_model=RefundPublic)
def reject_seller_refund(
    refund_id: int,
    payload: SellerRefundDecision | None = None,
    current_seller: Any = Depends(require_roles(UserRole.SELLER)),
    db: Any = Depends(get_db),
) -> RefundPublic:
    from app.services.commerce.service import review_seller_refund

    try:
        refund = review_seller_refund(
            db,
            current_seller,
            refund_id,
            approved=False,
            seller_note=payload.seller_note if payload else None,
        )
        db.commit()
        return refund
    except Exception:
        db.rollback()
        raise


@router.get("/reviews", response_model=ReviewListResponse)
def list_seller_reviews(
    spu_id: int | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_seller: Any = Depends(require_roles(UserRole.SELLER)),
    db: Any = Depends(get_db),
) -> ReviewListResponse:
    from app.services.commerce.service import list_reviews

    return list_reviews(db, user=current_seller, spu_id=spu_id, page=page, page_size=page_size)


@router.get("/reviews/products", response_model=ReviewProductListResponse)
def list_seller_review_products(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_seller: Any = Depends(require_roles(UserRole.SELLER)),
    db: Any = Depends(get_db),
) -> ReviewProductListResponse:
    from app.services.commerce.service import list_review_products

    return list_review_products(db, current_seller, page=page, page_size=page_size)


@router.post("/reviews/{review_id}/reply", response_model=ReviewPublic)
def reply_review(
    review_id: int,
    payload: ReviewReply,
    current_seller: Any = Depends(require_roles(UserRole.SELLER)),
    db: Any = Depends(get_db),
) -> ReviewPublic:
    from app.services.commerce.service import reply_product_review

    try:
        review = reply_product_review(
            db,
            current_seller,
            review_id=review_id,
            seller_reply=payload.seller_reply,
        )
        db.commit()
        return review
    except Exception:
        db.rollback()
        raise


@router.delete("/reviews/{review_id}/reply", response_model=ReviewPublic)
def delete_review_reply(
    review_id: int,
    current_seller: Any = Depends(require_roles(UserRole.SELLER)),
    db: Any = Depends(get_db),
) -> ReviewPublic:
    from app.services.commerce.service import delete_product_review_reply

    try:
        review = delete_product_review_reply(db, current_seller, review_id=review_id)
        db.commit()
        return review
    except Exception:
        db.rollback()
        raise
