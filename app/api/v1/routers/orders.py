from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import require_roles
from app.db.session import get_db
from app.models.enums import OrderStatus, UserRole
from app.schemas.order import DirectOrderCreate, OrderCreate, OrderCreateResponse, OrderDetail, OrderListResponse
from app.schemas.review import ReviewCreate, ReviewListResponse, ReviewPublic
from app.schemas.wallet import WalletLedgerListResponse, WalletPublic, WalletRechargeRequest


router = APIRouter()


def _is_integrity_error(exc: Exception) -> bool:
    return exc.__class__.__name__ == "IntegrityError"


@router.get("/wallet", response_model=WalletPublic)
def get_wallet(
    current_buyer: Any = Depends(require_roles(UserRole.BUYER)),
    db: Any = Depends(get_db),
) -> WalletPublic:
    from app.services.commerce.service import get_wallet

    return WalletPublic.model_validate(get_wallet(db, current_buyer))


@router.post("/wallet/recharge", response_model=WalletPublic)
def recharge_wallet(
    payload: WalletRechargeRequest,
    current_buyer: Any = Depends(require_roles(UserRole.BUYER)),
    db: Any = Depends(get_db),
) -> WalletPublic:
    from app.services.commerce.service import recharge_wallet

    try:
        wallet = recharge_wallet(
            db,
            current_buyer,
            payload.amount,
            payload.idempotency_key,
        )
        db.commit()
        db.refresh(wallet)
        return WalletPublic.model_validate(wallet)
    except Exception:
        db.rollback()
        raise


@router.get("/wallet/ledger", response_model=WalletLedgerListResponse)
def list_wallet_ledger(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_buyer: Any = Depends(require_roles(UserRole.BUYER)),
    db: Any = Depends(get_db),
) -> WalletLedgerListResponse:
    from app.services.commerce.service import list_wallet_ledgers

    return list_wallet_ledgers(db, current_buyer, page=page, page_size=page_size)


@router.get("", response_model=OrderListResponse)
def list_orders(
    status_filter: OrderStatus | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_buyer: Any = Depends(require_roles(UserRole.BUYER)),
    db: Any = Depends(get_db),
) -> OrderListResponse:
    from app.services.commerce.service import list_orders as load_orders

    try:
        response = load_orders(
            db,
            current_buyer,
            status_filter=status_filter,
            page=page,
            page_size=page_size,
        )
        db.commit()
        return response
    except Exception:
        db.rollback()
        raise


@router.post("", response_model=OrderCreateResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderCreate,
    current_buyer: Any = Depends(require_roles(UserRole.BUYER)),
    db: Any = Depends(get_db),
) -> OrderCreateResponse:
    from app.services.commerce.service import create_orders_from_cart

    try:
        orders = create_orders_from_cart(
            db,
            current_buyer,
            receiver_snapshot=payload.receiver_snapshot.model_dump(),
            idempotency_key=payload.idempotency_key,
            cart_item_ids=payload.cart_item_ids,
            auto_pay=payload.auto_pay,
        )
        db.commit()
        return OrderCreateResponse(orders=orders)
    except Exception:
        db.rollback()
        raise


@router.post("/direct", response_model=OrderDetail, status_code=status.HTTP_201_CREATED)
def create_direct_order(
    payload: DirectOrderCreate,
    current_buyer: Any = Depends(require_roles(UserRole.BUYER)),
    db: Any = Depends(get_db),
) -> OrderDetail:
    from app.services.commerce.service import create_order_from_sku

    try:
        order = create_order_from_sku(
            db,
            current_buyer,
            receiver_snapshot=payload.receiver_snapshot.model_dump(),
            idempotency_key=payload.idempotency_key,
            sku_id=payload.sku_id,
            quantity=payload.quantity,
            auto_pay=payload.auto_pay,
        )
        db.commit()
        return order
    except Exception:
        db.rollback()
        raise


@router.get("/reviews", response_model=ReviewListResponse)
def list_my_reviews(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_buyer: Any = Depends(require_roles(UserRole.BUYER)),
    db: Any = Depends(get_db),
) -> ReviewListResponse:
    from app.services.commerce.service import list_reviews

    return list_reviews(db, user=current_buyer, page=page, page_size=page_size)


@router.post("/reviews", response_model=ReviewPublic, status_code=status.HTTP_201_CREATED)
def create_review(
    payload: ReviewCreate,
    current_buyer: Any = Depends(require_roles(UserRole.BUYER)),
    db: Any = Depends(get_db),
) -> ReviewPublic:
    from app.services.commerce.service import create_product_review

    try:
        review = create_product_review(
            db,
            current_buyer,
            order_item_id=payload.order_item_id,
            rating=payload.rating,
            content=payload.content,
            images_json=payload.images_json,
        )
        db.commit()
        try:
            from app.services.search.service import upsert_product_search_document

            upsert_product_search_document(db, review.spu_id)
        except Exception:
            pass
        return review
    except Exception as exc:
        db.rollback()
        if _is_integrity_error(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Order item already reviewed.",
            ) from exc
        raise


@router.get("/{order_id}", response_model=OrderDetail)
def get_order(
    order_id: int,
    current_buyer: Any = Depends(require_roles(UserRole.BUYER)),
    db: Any = Depends(get_db),
) -> OrderDetail:
    from app.services.commerce.service import get_order_detail as load_order_detail

    try:
        order = load_order_detail(db, current_buyer, order_id)
        db.commit()
        return order
    except Exception:
        db.rollback()
        raise


@router.post("/{order_id}/cancel", response_model=OrderDetail)
def cancel_order(
    order_id: int,
    current_buyer: Any = Depends(require_roles(UserRole.BUYER)),
    db: Any = Depends(get_db),
) -> OrderDetail:
    from app.services.commerce.service import cancel_order

    try:
        order = cancel_order(db, current_buyer, order_id)
        db.commit()
        return order
    except Exception:
        db.rollback()
        raise


@router.post("/{order_id}/pay", response_model=OrderDetail)
def pay_order(
    order_id: int,
    current_buyer: Any = Depends(require_roles(UserRole.BUYER)),
    db: Any = Depends(get_db),
) -> OrderDetail:
    from app.services.commerce.service import pay_order

    try:
        order = pay_order(db, current_buyer, order_id)
        db.commit()
        return order
    except Exception:
        db.rollback()
        raise


@router.post("/{order_id}/complete", response_model=OrderDetail)
def complete_order(
    order_id: int,
    current_buyer: Any = Depends(require_roles(UserRole.BUYER)),
    db: Any = Depends(get_db),
) -> OrderDetail:
    from app.services.commerce.service import complete_order

    try:
        order = complete_order(db, current_buyer, order_id)
        db.commit()
        return order
    except Exception:
        db.rollback()
        raise
