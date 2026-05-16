from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import and_, case, func, or_, select

from app.models.enums import (
    DisputeStatus,
    LedgerDirection,
    MerchantAuditStatus,
    OrderStatus,
    ProductStatus,
    RefundStatus,
    ReviewStatus,
    UserRole,
    UserStatus,
    WalletBizType,
    WalletStatus,
)
from app.models.order import (
    Cart,
    CartItem,
    Order,
    OrderItem,
    OrderStatusLog,
    RefundApplication,
    RefundDispute,
)
from app.models.product import ProductReview, ProductSku, ProductSpu
from app.models.user import MerchantProfile, UserAccount
from app.models.wallet import WalletAccount, WalletLedger
from app.schemas.cart import CartItemPublic, CartPublic
from app.schemas.dispute import DisputeListResponse, DisputePublic
from app.schemas.order import OrderDetail, OrderItemPublic, OrderListResponse, OrderPublic
from app.schemas.refund import RefundListResponse, RefundPublic
from app.schemas.review import ReviewListResponse, ReviewProductListResponse, ReviewProductSummary, ReviewPublic
from app.schemas.wallet import SellerEarningsPublic, WalletLedgerListResponse, WalletLedgerPublic, WalletPublic


REFUND_SELLER_RESPONSE_DAYS = 3
WALLET_BALANCE_LIMIT = Decimal("9999999999.99")
ACTIVE_REFUND_STATUSES = (
    RefundStatus.PENDING,
    RefundStatus.REJECTED,
    RefundStatus.DISPUTED,
)


def _role_value(user: Any) -> str:
    return getattr(user.role, "value", user.role)


def _ensure_buyer(user: Any) -> None:
    if _role_value(user) != UserRole.BUYER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Buyer permission required.",
        )


def _ensure_seller_merchant(user: Any) -> MerchantProfile:
    if _role_value(user) != UserRole.SELLER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seller permission required.",
        )
    merchant = getattr(user, "merchant_profile", None)
    if merchant is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seller profile is missing.",
        )
    merchant_status = getattr(merchant.audit_status, "value", merchant.audit_status)
    if merchant_status != MerchantAuditStatus.APPROVED.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Merchant account is not approved yet.",
        )
    return merchant


def _ensure_admin(user: Any) -> None:
    if _role_value(user) != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permission required.",
        )


def _merchant_is_active_for_sales(merchant: MerchantProfile | None, seller_user: UserAccount | None) -> bool:
    merchant_status = getattr(getattr(merchant, "audit_status", None), "value", getattr(merchant, "audit_status", None))
    seller_status = getattr(getattr(seller_user, "status", None), "value", getattr(seller_user, "status", None))
    return (
        merchant_status == MerchantAuditStatus.APPROVED.value
        and seller_status == UserStatus.ACTIVE.value
    )


def _ensure_order_seller_can_receive_payment(db: Any, order: Order) -> None:
    row = db.execute(
        select(MerchantProfile, UserAccount)
        .join(UserAccount, MerchantProfile.user_id == UserAccount.id)
        .where(MerchantProfile.id == order.seller_id)
    ).first()
    if row is None or not _merchant_is_active_for_sales(row.MerchantProfile, row.UserAccount):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seller account is not available for payment.",
        )


def _get_or_create_cart(db: Any, buyer_id: int) -> Cart:
    cart = db.execute(
        select(Cart)
        .where(Cart.buyer_id == buyer_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if cart is not None:
        return cart
    cart = Cart(buyer_id=buyer_id)
    db.add(cart)
    db.flush()
    return cart


def _get_wallet_for_update(db: Any, user_id: int) -> WalletAccount:
    statement = (
        select(WalletAccount)
        .where(WalletAccount.user_id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    wallet = db.execute(statement).scalar_one_or_none()
    if wallet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet account not found.",
        )
    if wallet.status != WalletStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Wallet account is not active.",
        )
    return wallet


def get_wallet(db: Any, user: Any) -> WalletAccount:
    statement = select(WalletAccount).where(WalletAccount.user_id == user.id)
    wallet = db.execute(statement).scalar_one_or_none()
    if wallet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet account not found.",
        )
    return wallet


def get_seller_wallet(db: Any, seller: Any) -> WalletAccount:
    _ensure_seller_merchant(seller)
    return get_wallet(db, seller)


def get_seller_earnings(db: Any, seller: Any) -> SellerEarningsPublic:
    merchant = _ensure_seller_merchant(seller)
    wallet = get_wallet(db, seller)

    wallet_filters = (WalletLedger.wallet_account_id == wallet.id,)
    settlement_filters = (
        *wallet_filters,
        WalletLedger.biz_type == WalletBizType.SELLER_SETTLEMENT,
        WalletLedger.direction == LedgerDirection.IN,
    )
    total_settled_amount = db.execute(
        select(
            func.coalesce(
                func.sum(
                    case(
                        (
                            and_(
                                WalletLedger.biz_type == WalletBizType.SELLER_SETTLEMENT,
                                WalletLedger.direction == LedgerDirection.IN,
                            ),
                            WalletLedger.amount,
                        ),
                        (
                            and_(
                                WalletLedger.biz_type == WalletBizType.REFUND,
                                WalletLedger.direction == LedgerDirection.OUT,
                            ),
                            -WalletLedger.amount,
                        ),
                        else_=Decimal("0.00"),
                    )
                ),
                Decimal("0.00"),
            )
        ).where(*wallet_filters)
    ).scalar_one()
    settled_order_count = db.execute(
        select(func.count(WalletLedger.id)).where(*settlement_filters)
    ).scalar_one()
    last_settlement_at = db.execute(
        select(func.max(WalletLedger.created_at)).where(*settlement_filters)
    ).scalar_one()

    pending_order_filters = (
        Order.seller_id == merchant.id,
        Order.status.in_([OrderStatus.PAID, OrderStatus.SHIPPED]),
    )
    pending_settlement_amount = db.execute(
        select(func.coalesce(func.sum(Order.payable_amount), Decimal("0.00"))).where(*pending_order_filters)
    ).scalar_one()
    pending_order_count = db.execute(
        select(func.count(Order.id)).where(*pending_order_filters)
    ).scalar_one()

    return SellerEarningsPublic(
        wallet=WalletPublic.model_validate(wallet),
        merchant_id=merchant.id,
        total_settled_amount=total_settled_amount,
        settled_order_count=settled_order_count,
        pending_settlement_amount=pending_settlement_amount,
        pending_order_count=pending_order_count,
        last_settlement_at=last_settlement_at,
    )


def _wallet_ledger_title(ledger: WalletLedger) -> str:
    if ledger.biz_type == WalletBizType.RECHARGE:
        return "系统充值"
    if ledger.biz_type == WalletBizType.ORDER_PAY and ledger.direction == LedgerDirection.OUT:
        return "订单支付"
    if ledger.biz_type == WalletBizType.REFUND and ledger.direction in {LedgerDirection.IN, LedgerDirection.UNFREEZE}:
        return "退款到账"
    if ledger.biz_type == WalletBizType.REFUND and ledger.direction == LedgerDirection.OUT:
        return "退款支出"
    if ledger.biz_type == WalletBizType.SELLER_SETTLEMENT:
        return "订单入账"
    return "钱包变动"


def _signed_ledger_amount(ledger: WalletLedger) -> Decimal:
    if ledger.direction == LedgerDirection.OUT:
        return -ledger.amount
    return ledger.amount


def _ledger_order_ids(db: Any, ledgers: Sequence[WalletLedger]) -> dict[int, int | None]:
    order_by_ledger_id: dict[int, int | None] = {}
    refund_ids: set[int] = set()
    dispute_ids: set[int] = set()

    for ledger in ledgers:
        reference_type = ledger.reference_type or ""
        if reference_type in {"order_pay", "order_cancel", "order_complete"}:
            order_by_ledger_id[ledger.id] = ledger.reference_id
        elif reference_type.startswith("refund_dispute"):
            dispute_ids.add(ledger.reference_id)
        elif reference_type.startswith("refund"):
            refund_ids.add(ledger.reference_id)
        else:
            order_by_ledger_id[ledger.id] = None

    refund_order_ids = {
        refund.id: refund.order_id
        for refund in db.execute(
            select(RefundApplication).where(RefundApplication.id.in_(refund_ids))
        ).scalars().all()
    } if refund_ids else {}
    dispute_order_ids = {
        dispute.id: dispute.order_id
        for dispute in db.execute(
            select(RefundDispute).where(RefundDispute.id.in_(dispute_ids))
        ).scalars().all()
    } if dispute_ids else {}

    for ledger in ledgers:
        if ledger.id in order_by_ledger_id:
            continue
        reference_type = ledger.reference_type or ""
        if reference_type.startswith("refund_dispute"):
            order_by_ledger_id[ledger.id] = dispute_order_ids.get(ledger.reference_id)
        elif reference_type.startswith("refund"):
            order_by_ledger_id[ledger.id] = refund_order_ids.get(ledger.reference_id)
        else:
            order_by_ledger_id[ledger.id] = None

    return order_by_ledger_id


def list_wallet_ledgers(
    db: Any,
    user: Any,
    *,
    page: int = 1,
    page_size: int = 20,
) -> WalletLedgerListResponse:
    wallet = get_wallet(db, user)
    user_role = _role_value(user)

    if user_role == UserRole.BUYER.value:
        visible_filters = or_(
            and_(WalletLedger.biz_type == WalletBizType.RECHARGE, WalletLedger.direction == LedgerDirection.IN),
            and_(WalletLedger.biz_type == WalletBizType.ORDER_PAY, WalletLedger.direction == LedgerDirection.OUT),
            and_(
                WalletLedger.biz_type == WalletBizType.REFUND,
                WalletLedger.direction.in_([LedgerDirection.IN, LedgerDirection.UNFREEZE]),
            ),
        )
    elif user_role == UserRole.SELLER.value:
        _ensure_seller_merchant(user)
        visible_filters = or_(
            and_(WalletLedger.biz_type == WalletBizType.SELLER_SETTLEMENT, WalletLedger.direction == LedgerDirection.IN),
            and_(WalletLedger.biz_type == WalletBizType.REFUND, WalletLedger.direction == LedgerDirection.OUT),
        )
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Wallet ledger permission required.")

    base_statement = select(WalletLedger.id).where(
        WalletLedger.wallet_account_id == wallet.id,
        visible_filters,
    )
    total = db.execute(select(func.count()).select_from(base_statement.subquery())).scalar_one()
    ledgers = db.execute(
        select(WalletLedger)
        .where(WalletLedger.wallet_account_id == wallet.id, visible_filters)
        .order_by(WalletLedger.created_at.desc(), WalletLedger.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()
    order_ids = _ledger_order_ids(db, ledgers)

    return WalletLedgerListResponse(
        items=[
            WalletLedgerPublic(
                id=ledger.id,
                biz_type=ledger.biz_type,
                direction=ledger.direction,
                title=_wallet_ledger_title(ledger),
                amount=ledger.amount,
                signed_amount=_signed_ledger_amount(ledger),
                reference_type=ledger.reference_type,
                reference_id=ledger.reference_id,
                order_id=order_ids.get(ledger.id),
                created_at=ledger.created_at,
            )
            for ledger in ledgers
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


def _has_ledger_for_wallet(
    db: Any,
    wallet_id: int,
    *,
    reference_type: str,
    reference_id: int,
    biz_type: WalletBizType,
) -> bool:
    statement = (
        select(WalletLedger.id)
        .where(
            WalletLedger.wallet_account_id == wallet_id,
            WalletLedger.reference_type == reference_type,
            WalletLedger.reference_id == reference_id,
            WalletLedger.biz_type == biz_type,
        )
        .limit(1)
    )
    return db.execute(statement).first() is not None


def _write_ledger(
    db: Any,
    wallet: WalletAccount,
    *,
    biz_type: WalletBizType,
    direction: LedgerDirection,
    amount: Decimal,
    before_available: Decimal,
    before_frozen: Decimal,
    reference_type: str,
    reference_id: int,
) -> None:
    db.add(
        WalletLedger(
            wallet_account_id=wallet.id,
            biz_type=biz_type,
            direction=direction,
            amount=amount,
            before_available_balance=before_available,
            after_available_balance=wallet.available_balance,
            before_frozen_balance=before_frozen,
            after_frozen_balance=wallet.frozen_balance,
            reference_type=reference_type,
            reference_id=reference_id,
        )
    )


def _ensure_wallet_balance_limit(available_balance: Decimal, frozen_balance: Decimal) -> None:
    if available_balance > WALLET_BALANCE_LIMIT or frozen_balance > WALLET_BALANCE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wallet balance limit exceeded.",
        )


def _apply_wallet_change(
    db: Any,
    *,
    user_id: int,
    amount: Decimal,
    biz_type: WalletBizType,
    direction: LedgerDirection,
    available_delta: Decimal,
    frozen_delta: Decimal,
    reference_type: str,
    reference_id: int,
    insufficient_available_detail: str | None = None,
    insufficient_frozen_detail: str | None = None,
) -> WalletAccount:
    wallet = _get_wallet_for_update(db, user_id)
    if _has_ledger_for_wallet(
        db,
        wallet.id,
        reference_type=reference_type,
        reference_id=reference_id,
        biz_type=biz_type,
    ):
        return wallet

    if available_delta < 0 and wallet.available_balance < abs(available_delta):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=insufficient_available_detail or "Insufficient wallet balance.",
        )
    if frozen_delta < 0 and wallet.frozen_balance < abs(frozen_delta):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=insufficient_frozen_detail or "Insufficient frozen wallet balance.",
        )

    before_available = wallet.available_balance
    before_frozen = wallet.frozen_balance
    next_available = wallet.available_balance + available_delta
    next_frozen = wallet.frozen_balance + frozen_delta
    _ensure_wallet_balance_limit(next_available, next_frozen)
    wallet.available_balance = next_available
    wallet.frozen_balance = next_frozen
    wallet.version += 1
    _write_ledger(
        db,
        wallet,
        biz_type=biz_type,
        direction=direction,
        amount=amount,
        before_available=before_available,
        before_frozen=before_frozen,
        reference_type=reference_type,
        reference_id=reference_id,
    )
    return wallet


def _wallet_recharge_reference_id(idempotency_key: str) -> int:
    digest = hashlib.sha256(idempotency_key.strip().encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)


def recharge_wallet(
    db: Any,
    user: Any,
    amount: Decimal,
    idempotency_key: str,
) -> WalletAccount:
    reference_id = _wallet_recharge_reference_id(idempotency_key)
    wallet = _apply_wallet_change(
        db,
        user_id=user.id,
        amount=amount,
        biz_type=WalletBizType.RECHARGE,
        direction=LedgerDirection.IN,
        available_delta=amount,
        frozen_delta=Decimal("0.00"),
        reference_type="wallet_recharge",
        reference_id=reference_id,
    )
    db.flush()
    return wallet


def _freeze_wallet_amount(
    db: Any,
    user_id: int,
    amount: Decimal,
    *,
    reference_type: str,
    reference_id: int,
    allow_partial: bool = False,
) -> WalletAccount:
    return _apply_wallet_change(
        db,
        user_id=user_id,
        amount=amount,
        biz_type=WalletBizType.ORDER_PAY,
        direction=LedgerDirection.FREEZE,
        available_delta=-amount,
        frozen_delta=amount,
        reference_type=reference_type,
        reference_id=reference_id,
        insufficient_available_detail=(
            "Insufficient wallet balance; order transaction was not created."
            if allow_partial
            else "Insufficient wallet balance."
        ),
    )


def _settle_frozen_amount(
    db: Any,
    user_id: int,
    amount: Decimal,
    *,
    reference_type: str,
    reference_id: int,
) -> WalletAccount:
    return _apply_wallet_change(
        db,
        user_id=user_id,
        amount=amount,
        biz_type=WalletBizType.ORDER_PAY,
        direction=LedgerDirection.OUT,
        available_delta=Decimal("0.00"),
        frozen_delta=-amount,
        reference_type=reference_type,
        reference_id=reference_id,
    )


def _refund_frozen_amount(
    db: Any,
    user_id: int,
    amount: Decimal,
    *,
    reference_type: str,
    reference_id: int,
) -> WalletAccount:
    return _apply_wallet_change(
        db,
        user_id=user_id,
        amount=amount,
        biz_type=WalletBizType.REFUND,
        direction=LedgerDirection.UNFREEZE,
        available_delta=amount,
        frozen_delta=-amount,
        reference_type=reference_type,
        reference_id=reference_id,
    )


def _settle_seller_income(
    db: Any,
    user_id: int,
    amount: Decimal,
    *,
    reference_type: str,
    reference_id: int,
) -> WalletAccount:
    return _apply_wallet_change(
        db,
        user_id=user_id,
        amount=amount,
        biz_type=WalletBizType.SELLER_SETTLEMENT,
        direction=LedgerDirection.IN,
        available_delta=amount,
        frozen_delta=Decimal("0.00"),
        reference_type=reference_type,
        reference_id=reference_id,
    )


def _debit_available_amount(
    db: Any,
    user_id: int,
    amount: Decimal,
    *,
    reference_type: str,
    reference_id: int,
    insufficient_available_detail: str | None = None,
) -> WalletAccount:
    return _apply_wallet_change(
        db,
        user_id=user_id,
        amount=amount,
        biz_type=WalletBizType.REFUND,
        direction=LedgerDirection.OUT,
        available_delta=-amount,
        frozen_delta=Decimal("0.00"),
        reference_type=reference_type,
        reference_id=reference_id,
        insufficient_available_detail=insufficient_available_detail,
    )


def _credit_available_amount(
    db: Any,
    user_id: int,
    amount: Decimal,
    *,
    reference_type: str,
    reference_id: int,
) -> WalletAccount:
    return _apply_wallet_change(
        db,
        user_id=user_id,
        amount=amount,
        biz_type=WalletBizType.REFUND,
        direction=LedgerDirection.IN,
        available_delta=amount,
        frozen_delta=Decimal("0.00"),
        reference_type=reference_type,
        reference_id=reference_id,
    )


def _cart_item_rows(db: Any, cart_id: int, item_ids: Sequence[int] | None = None) -> list[Any]:
    filters = [CartItem.cart_id == cart_id]
    if item_ids is not None:
        filters.append(CartItem.id.in_(item_ids))
    statement = (
        select(
            CartItem,
            ProductSku,
            ProductSpu,
            MerchantProfile,
            UserAccount,
            MerchantProfile.shop_name.label("shop_name"),
        )
        .join(ProductSku, CartItem.sku_id == ProductSku.id)
        .join(ProductSpu, ProductSku.spu_id == ProductSpu.id)
        .join(MerchantProfile, ProductSpu.merchant_id == MerchantProfile.id)
        .join(UserAccount, MerchantProfile.user_id == UserAccount.id)
        .where(and_(*filters))
        .order_by(CartItem.created_at.desc(), CartItem.id.desc())
    )
    return db.execute(statement).all()


def _cart_items_for_update(db: Any, cart_id: int, item_ids: Sequence[int] | None = None) -> list[CartItem]:
    filters = [CartItem.cart_id == cart_id]
    if item_ids is not None:
        filters.append(CartItem.id.in_(item_ids))
    statement = (
        select(CartItem)
        .where(and_(*filters))
        .order_by(CartItem.id.asc())
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return db.execute(statement).scalars().all()


def _row_to_cart_item(row: Any) -> CartItemPublic:
    item: CartItem = row.CartItem
    sku: ProductSku = row.ProductSku
    spu: ProductSpu = row.ProductSpu
    line_amount = sku.price * item.quantity
    available = (
        spu.status == ProductStatus.ONLINE
        and _merchant_is_active_for_sales(row.MerchantProfile, row.UserAccount)
        and sku.stock_available >= item.quantity
        and sku.stock_available >= 0
    )
    return CartItemPublic(
        id=item.id,
        sku_id=item.sku_id,
        spu_id=sku.spu_id,
        merchant_id=spu.merchant_id,
        merchant_shop_name=row.shop_name,
        product_name=spu.name,
        spec_name=sku.spec_name,
        spec_attrs_json=sku.spec_attrs_json,
        cover_image_url=spu.cover_image_url,
        unit=sku.unit,
        unit_price=sku.price,
        quantity=item.quantity,
        selected=item.selected,
        line_amount=line_amount,
        stock_available=sku.stock_available,
        stock_locked=sku.stock_locked,
        available=available,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def get_cart(db: Any, buyer: Any) -> CartPublic:
    _ensure_buyer(buyer)
    cart = _get_or_create_cart(db, buyer.id)
    rows = _cart_item_rows(db, cart.id)
    items = [_row_to_cart_item(row) for row in rows]
    return CartPublic(
        id=cart.id,
        buyer_id=cart.buyer_id,
        items=items,
        total_quantity=sum(item.quantity for item in items),
        total_amount=sum((item.line_amount for item in items), Decimal("0.00")),
        selected_amount=sum(
            (item.line_amount for item in items if item.selected),
            Decimal("0.00"),
        ),
    )


def add_cart_item(db: Any, buyer: Any, *, sku_id: int, quantity: int, selected: bool = True) -> CartPublic:
    _ensure_buyer(buyer)
    sku = db.get(ProductSku, sku_id)
    if sku is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SKU not found.")
    spu = db.get(ProductSpu, sku.spu_id)
    if spu is None or spu.status != ProductStatus.ONLINE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Product is not online.")
    if sku.stock_available < quantity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient SKU stock.")

    cart = _get_or_create_cart(db, buyer.id)
    item = db.execute(
        select(CartItem).where(CartItem.cart_id == cart.id, CartItem.sku_id == sku_id)
    ).scalar_one_or_none()
    if item is None:
        db.add(CartItem(cart_id=cart.id, sku_id=sku_id, quantity=quantity, selected=selected))
    else:
        item.quantity += quantity
        item.selected = selected
        if sku.stock_available < item.quantity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient SKU stock.")
    db.flush()
    return get_cart(db, buyer)


def update_cart_item(db: Any, buyer: Any, item_id: int, *, quantity: int | None, selected: bool | None) -> CartPublic:
    _ensure_buyer(buyer)
    cart = _get_or_create_cart(db, buyer.id)
    item = db.execute(
        select(CartItem).where(CartItem.id == item_id, CartItem.cart_id == cart.id)
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found.")
    if quantity is not None:
        sku = db.get(ProductSku, item.sku_id)
        if sku is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SKU not found.")
        if sku.stock_available < quantity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient SKU stock.")
        item.quantity = quantity
    if selected is not None:
        item.selected = selected
    db.flush()
    return get_cart(db, buyer)


def remove_cart_item(db: Any, buyer: Any, item_id: int) -> CartPublic:
    _ensure_buyer(buyer)
    cart = _get_or_create_cart(db, buyer.id)
    item = db.execute(
        select(CartItem).where(CartItem.id == item_id, CartItem.cart_id == cart.id)
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found.")
    db.delete(item)
    db.flush()
    return get_cart(db, buyer)


def _generate_order_no() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    return f"SO{timestamp}{uuid4().hex[:10].upper()}"


def _split_order_idempotency_key(base_key: str, seller_id: int, split_count: int) -> str:
    if split_count <= 1:
        return base_key
    return f"{base_key}.{seller_id}"


def _lock_sku(db: Any, sku_id: int) -> ProductSku:
    sku = db.execute(
        select(ProductSku)
        .where(ProductSku.id == sku_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if sku is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SKU not found.")
    return sku


def _write_order_status_log(
    db: Any,
    order: Order,
    *,
    from_status: OrderStatus | None,
    to_status: OrderStatus,
    operator_id: int | None,
    note: str | None = None,
) -> None:
    db.add(
        OrderStatusLog(
            order_id=order.id,
            from_status=from_status,
            to_status=to_status,
            operator_id=operator_id,
            note=note,
        )
    )


def _payment_deadline_reached(expires_at: datetime | None, now: datetime) -> bool:
    if expires_at is None:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at <= now


def _refund_deadline_reached(deadline_at: datetime | None, now: datetime) -> bool:
    if deadline_at is None:
        return False
    if deadline_at.tzinfo is None:
        deadline_at = deadline_at.replace(tzinfo=UTC)
    return deadline_at <= now


def _expire_wait_pay_order_locked(db: Any, order: Order, *, now: datetime | None = None) -> bool:
    now = now or datetime.now(UTC)
    if order.status != OrderStatus.WAIT_PAY:
        return False
    if not _payment_deadline_reached(order.payment_expires_at, now):
        return False
    before_status = order.status
    _release_order_locked_stock(db, order)
    order.status = OrderStatus.EXPIRED
    _write_order_status_log(
        db,
        order,
        from_status=before_status,
        to_status=OrderStatus.EXPIRED,
        operator_id=None,
        note="Payment window expired; locked stock released.",
    )
    return True


def _expire_overdue_wait_pay_orders(db: Any, user: Any) -> int:
    now = datetime.now(UTC)
    filters = [
        Order.status == OrderStatus.WAIT_PAY,
        Order.payment_expires_at.is_not(None),
        Order.payment_expires_at <= now,
    ]
    role = _role_value(user)
    if role == UserRole.BUYER.value:
        filters.append(Order.buyer_id == user.id)
    elif role == UserRole.SELLER.value:
        return 0
    elif role != UserRole.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unsupported role.")

    expired_count = 0
    statement = (
        select(Order)
        .where(and_(*filters))
        .order_by(Order.id.asc())
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    for order in db.execute(statement).scalars().all():
        if _expire_wait_pay_order_locked(db, order, now=now):
            expired_count += 1
    if expired_count:
        db.flush()
    return expired_count


def _create_refund_dispute_locked(
    db: Any,
    refund: RefundApplication,
    order: Order,
    *,
    initiator_id: int,
    initiator_role: UserRole,
    reason: str,
    description: str | None,
    evidence_images_json: list[str] | None,
) -> RefundDispute:
    existing = db.execute(
        select(RefundDispute)
        .where(RefundDispute.refund_id == refund.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    dispute = RefundDispute(
        refund_id=refund.id,
        order_id=refund.order_id,
        buyer_id=refund.buyer_id,
        seller_id=refund.seller_id,
        initiator_id=initiator_id,
        initiator_role=initiator_role,
        status=DisputeStatus.PENDING,
        reason=reason,
        description=description,
        evidence_images_json=evidence_images_json,
        resolution_note=None,
        resolved_by=None,
        resolved_at=None,
    )
    db.add(dispute)
    refund.status = RefundStatus.DISPUTED
    db.flush()
    return dispute


def _escalate_overdue_refunds(
    db: Any,
    *,
    user: Any | None = None,
    refund_id: int | None = None,
) -> int:
    now = datetime.now(UTC)
    filters = [
        RefundApplication.status == RefundStatus.PENDING,
        RefundApplication.seller_deadline_at.is_not(None),
        RefundApplication.seller_deadline_at <= now,
    ]
    if refund_id is not None:
        filters.append(RefundApplication.id == refund_id)
    if user is not None:
        role = _role_value(user)
        if role == UserRole.BUYER.value:
            filters.append(RefundApplication.buyer_id == user.id)
        elif role == UserRole.SELLER.value:
            merchant = _ensure_seller_merchant(user)
            filters.append(RefundApplication.seller_id == merchant.id)
        elif role != UserRole.ADMIN.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unsupported role.")

    escalated_count = 0
    refunds = db.execute(
        select(RefundApplication)
        .where(and_(*filters))
        .order_by(RefundApplication.id.asc())
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalars().all()
    for refund in refunds:
        order = _get_order_for_update(db, refund.order_id)
        dispute = _create_refund_dispute_locked(
            db,
            refund,
            order,
            initiator_id=refund.buyer_id,
            initiator_role=UserRole.BUYER,
            reason="Seller response timed out.",
            description="Seller did not handle the refund request within 3 days.",
            evidence_images_json=None,
        )
        if dispute.status == DisputeStatus.PENDING:
            escalated_count += 1
    if escalated_count:
        db.flush()
    return escalated_count


def escalate_overdue_refunds(db: Any, user: Any | None = None) -> int:
    return _escalate_overdue_refunds(db, user=user)


def _complete_refund_locked(
    db: Any,
    refund: RefundApplication,
    order: Order,
    *,
    reference_type: str,
    reference_id: int,
    operator_id: int | None,
    note: str,
) -> None:
    if not order.is_shipped:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only shipped orders can be refunded.")
    if order.status == OrderStatus.SHIPPED:
        _release_order_locked_stock(db, order)
        _refund_frozen_amount(
            db,
            order.buyer_id,
            refund.amount,
            reference_type=reference_type,
            reference_id=reference_id,
        )
    elif order.status == OrderStatus.COMPLETED:
        merchant = db.get(MerchantProfile, order.seller_id)
        if merchant is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Merchant profile not found.")
        _get_wallet_for_update(db, order.buyer_id)
        _debit_available_amount(
            db,
            merchant.user_id,
            refund.amount,
            reference_type=f"{reference_type}_seller",
            reference_id=reference_id,
            insufficient_available_detail=(
                "Seller wallet balance is insufficient to approve this refund."
            ),
        )
        _credit_available_amount(
            db,
            order.buyer_id,
            refund.amount,
            reference_type=f"{reference_type}_buyer",
            reference_id=reference_id,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only shipped or completed orders can be refunded.",
        )

    before_status = order.status
    refund.status = RefundStatus.COMPLETED
    order.status = OrderStatus.REFUNDED
    _write_order_status_log(
        db,
        order,
        from_status=before_status,
        to_status=OrderStatus.REFUNDED,
        operator_id=operator_id,
        note=note,
    )


def create_orders_from_cart(
    db: Any,
    buyer: Any,
    *,
    receiver_snapshot: dict,
    idempotency_key: str,
    cart_item_ids: Sequence[int] | None = None,
    auto_pay: bool = False,
) -> list[OrderDetail]:
    _ensure_buyer(buyer)
    cart = _get_or_create_cart(db, buyer.id)
    existing = db.execute(
        select(Order)
        .where(
            Order.buyer_id == buyer.id,
            or_(
                Order.checkout_idempotency_key == idempotency_key,
                Order.idempotency_key == idempotency_key,
            )
        )
        .order_by(Order.id.asc())
    ).scalars().all()
    if existing:
        return [get_order_detail(db, buyer, order.id) for order in existing]

    selected_ids = list(cart_item_ids) if cart_item_ids else None
    locked_items = _cart_items_for_update(db, cart.id, selected_ids)
    if selected_ids is not None and len(locked_items) != len(set(selected_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Some cart items are invalid.")
    rows = _cart_item_rows(db, cart.id, selected_ids)
    rows = [row for row in rows if row.CartItem.selected or selected_ids is not None]
    if not rows:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No cart items selected.")
    if selected_ids is not None and len(rows) != len(set(selected_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Some cart items are invalid.")

    grouped_rows: dict[int, list[Any]] = defaultdict(list)
    for row in rows:
        if row.ProductSpu.status != ProductStatus.ONLINE or not _merchant_is_active_for_sales(
            row.MerchantProfile,
            row.UserAccount,
        ):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart contains unavailable products.")
        grouped_rows[row.ProductSpu.merchant_id].append(row)

    created_orders: list[Order] = []
    now = datetime.now(UTC)
    expected_delivery_at = now + timedelta(days=3)
    payment_expires_at = now + timedelta(minutes=20)
    for seller_id, seller_rows in grouped_rows.items():
        total_amount = sum(
            (row.ProductSku.price * row.CartItem.quantity for row in seller_rows),
            Decimal("0.00"),
        )
        order = Order(
            order_no=_generate_order_no(),
            buyer_id=buyer.id,
            seller_id=seller_id,
            status=OrderStatus.WAIT_PAY,
            total_amount=total_amount,
            freight_amount=Decimal("0.00"),
            payable_amount=total_amount,
            receiver_snapshot_json=receiver_snapshot,
            expected_delivery_at=expected_delivery_at,
            payment_expires_at=payment_expires_at,
            paid_at=None,
            is_shipped=False,
            shipped_at=None,
            idempotency_key=_split_order_idempotency_key(
                idempotency_key,
                seller_id,
                len(grouped_rows),
            ),
            checkout_idempotency_key=idempotency_key,
        )
        db.add(order)
        db.flush()

        _write_order_status_log(
            db,
            order,
            from_status=None,
            to_status=OrderStatus.WAIT_PAY,
            operator_id=buyer.id,
            note="Order created and stock locked.",
        )

        for row in sorted(seller_rows, key=lambda item_row: item_row.ProductSku.id):
            item: CartItem = row.CartItem
            locked_sku = _lock_sku(db, item.sku_id)
            if locked_sku.stock_available < item.quantity:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient SKU stock.")
            locked_sku.stock_available -= item.quantity
            locked_sku.stock_locked += item.quantity
            locked_sku.version += 1
            db.add(
                OrderItem(
                    order_id=order.id,
                    spu_id=row.ProductSpu.id,
                    sku_id=locked_sku.id,
                    product_name_snapshot=row.ProductSpu.name,
                    spec_name_snapshot=locked_sku.spec_name,
                    cover_image_url_snapshot=row.ProductSpu.cover_image_url,
                    unit_price=locked_sku.price,
                    quantity=item.quantity,
                    total_amount=locked_sku.price * item.quantity,
                )
            )
            db.delete(item)

        created_orders.append(order)

    db.flush()
    if auto_pay:
        for order in created_orders:
            _pay_locked_order(db, buyer, order, allow_partial=True)

    db.flush()
    return [get_order_detail(db, buyer, order.id) for order in created_orders]


def create_order_from_sku(
    db: Any,
    buyer: Any,
    *,
    receiver_snapshot: dict,
    idempotency_key: str,
    sku_id: int,
    quantity: int = 1,
    auto_pay: bool = False,
) -> OrderDetail:
    _ensure_buyer(buyer)
    existing = db.execute(
        select(Order)
        .where(
            Order.buyer_id == buyer.id,
            or_(
                Order.checkout_idempotency_key == idempotency_key,
                Order.idempotency_key == idempotency_key,
            ),
        )
        .order_by(Order.id.asc())
    ).scalars().first()
    if existing is not None:
        return get_order_detail(db, buyer, existing.id)

    sku = _lock_sku(db, sku_id)
    spu = db.get(ProductSpu, sku.spu_id)
    if spu is None or spu.status != ProductStatus.ONLINE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Product is not online.")
    merchant = db.get(MerchantProfile, spu.merchant_id)
    seller_user = db.get(UserAccount, merchant.user_id) if merchant is not None else None
    if merchant is None or seller_user is None or not _merchant_is_active_for_sales(merchant, seller_user):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart contains unavailable products.")
    if sku.stock_available < quantity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient SKU stock.")

    now = datetime.now(UTC)
    order = Order(
        order_no=_generate_order_no(),
        buyer_id=buyer.id,
        seller_id=spu.merchant_id,
        status=OrderStatus.WAIT_PAY,
        total_amount=sku.price * quantity,
        freight_amount=Decimal("0.00"),
        payable_amount=sku.price * quantity,
        receiver_snapshot_json=receiver_snapshot,
        expected_delivery_at=now + timedelta(days=3),
        payment_expires_at=now + timedelta(minutes=20),
        paid_at=None,
        is_shipped=False,
        shipped_at=None,
        idempotency_key=idempotency_key,
        checkout_idempotency_key=idempotency_key,
    )
    db.add(order)
    db.flush()

    _write_order_status_log(
        db,
        order,
        from_status=None,
        to_status=OrderStatus.WAIT_PAY,
        operator_id=buyer.id,
        note="Direct order created and stock locked.",
    )

    sku.stock_available -= quantity
    sku.stock_locked += quantity
    sku.version += 1
    db.add(
        OrderItem(
            order_id=order.id,
            spu_id=spu.id,
            sku_id=sku.id,
            product_name_snapshot=spu.name,
            spec_name_snapshot=sku.spec_name,
            cover_image_url_snapshot=spu.cover_image_url,
            unit_price=sku.price,
            quantity=quantity,
            total_amount=sku.price * quantity,
        )
    )
    db.flush()
    if auto_pay:
        _pay_locked_order(db, buyer, order, allow_partial=True)
    db.flush()
    return get_order_detail(db, buyer, order.id)


def _order_item_rows(db: Any, order_id: int) -> list[OrderItem]:
    return db.execute(
        select(OrderItem).where(OrderItem.order_id == order_id).order_by(OrderItem.id.asc())
    ).scalars().all()


def _reviews_by_order_item(db: Any, order_item_ids: Sequence[int]) -> dict[int, ProductReview]:
    if not order_item_ids:
        return {}
    reviews = db.execute(
        select(ProductReview).where(ProductReview.order_item_id.in_(order_item_ids))
    ).scalars().all()
    return {review.order_item_id: review for review in reviews}


def _active_refunds_by_order_ids(db: Any, order_ids: Sequence[int]) -> dict[int, RefundApplication]:
    if not order_ids:
        return {}
    refunds = db.execute(
        select(RefundApplication)
        .where(
            RefundApplication.order_id.in_(order_ids),
            RefundApplication.status.in_(ACTIVE_REFUND_STATUSES),
        )
        .order_by(RefundApplication.created_at.desc(), RefundApplication.id.desc())
    ).scalars().all()
    result: dict[int, RefundApplication] = {}
    for refund in refunds:
        result.setdefault(refund.order_id, refund)
    return result


def _order_summary_from_items(items: Sequence[OrderItem]) -> dict[str, Any]:
    if not items:
        return {"primary_product_name": None, "item_count": 0}
    first_item = min(items, key=lambda item: item.id)
    return {
        "primary_product_name": first_item.product_name_snapshot,
        "item_count": len(items),
    }


def _order_summaries_by_order_ids(db: Any, order_ids: Sequence[int]) -> dict[int, dict[str, Any]]:
    if not order_ids:
        return {}
    items = db.execute(
        select(OrderItem)
        .where(OrderItem.order_id.in_(order_ids))
        .order_by(OrderItem.order_id.asc(), OrderItem.id.asc())
    ).scalars().all()
    grouped: dict[int, list[OrderItem]] = defaultdict(list)
    for item in items:
        grouped[item.order_id].append(item)
    return {
        order_id: _order_summary_from_items(order_items)
        for order_id, order_items in grouped.items()
    }


def _order_to_public(
    row: Any,
    active_refund: RefundApplication | None = None,
    summary: dict[str, Any] | None = None,
) -> OrderPublic:
    order: Order = row.Order
    summary = summary or {}
    return OrderPublic(
        id=order.id,
        order_no=order.order_no,
        primary_product_name=summary.get("primary_product_name"),
        item_count=summary.get("item_count", 0),
        buyer_id=order.buyer_id,
        buyer_username=getattr(row, "buyer_username", None),
        seller_id=order.seller_id,
        seller_shop_name=row.shop_name,
        status=order.status,
        total_amount=order.total_amount,
        freight_amount=order.freight_amount,
        payable_amount=order.payable_amount,
        expected_delivery_at=order.expected_delivery_at,
        payment_expires_at=order.payment_expires_at,
        paid_at=order.paid_at,
        is_shipped=order.is_shipped,
        shipped_at=order.shipped_at,
        active_refund_id=active_refund.id if active_refund else None,
        active_refund_status=active_refund.status if active_refund else None,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def _order_to_detail(db: Any, row: Any, items: Sequence[OrderItem]) -> OrderDetail:
    active_refund = _active_refunds_by_order_ids(db, [row.Order.id]).get(row.Order.id)
    public = _order_to_public(row, active_refund, _order_summary_from_items(items))
    reviews = _reviews_by_order_item(db, [item.id for item in items])
    sku_ids = {item.sku_id for item in items}
    skus = {
        sku.id: sku
        for sku in db.execute(select(ProductSku).where(ProductSku.id.in_(sku_ids))).scalars().all()
    } if sku_ids else {}
    return OrderDetail(
        **public.model_dump(),
        receiver_snapshot_json=row.Order.receiver_snapshot_json,
        items=[
            OrderItemPublic(
                id=item.id,
                spu_id=item.spu_id,
                sku_id=item.sku_id,
                product_name_snapshot=item.product_name_snapshot,
                spec_name_snapshot=item.spec_name_snapshot,
                sku_unit=skus[item.sku_id].unit if item.sku_id in skus else None,
                sku_spec_attrs_json=skus[item.sku_id].spec_attrs_json if item.sku_id in skus else None,
                cover_image_url_snapshot=item.cover_image_url_snapshot,
                unit_price=item.unit_price,
                quantity=item.quantity,
                total_amount=item.total_amount,
                review=(
                    ReviewPublic.model_validate(reviews[item.id])
                    if item.id in reviews
                    else None
                ),
            )
            for item in items
        ],
    )


def _order_query_for_user(user: Any):
    statement = (
        select(
            Order,
            MerchantProfile.shop_name.label("shop_name"),
            UserAccount.username.label("buyer_username"),
        )
        .join(MerchantProfile, Order.seller_id == MerchantProfile.id)
        .join(UserAccount, Order.buyer_id == UserAccount.id)
    )
    role = _role_value(user)
    if role == UserRole.BUYER.value:
        return statement.where(Order.buyer_id == user.id)
    if role == UserRole.SELLER.value:
        merchant = _ensure_seller_merchant(user)
        return statement.where(
            Order.seller_id == merchant.id,
            Order.paid_at.is_not(None),
        )
    if role == UserRole.ADMIN.value:
        return statement
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unsupported role.")


def list_orders(
    db: Any,
    user: Any,
    *,
    status_filter: OrderStatus | None = None,
    page: int = 1,
    page_size: int = 20,
) -> OrderListResponse:
    _expire_overdue_wait_pay_orders(db, user)
    _escalate_overdue_refunds(db, user=user)
    statement = _order_query_for_user(user)
    if status_filter is not None:
        statement = statement.where(Order.status == status_filter)
    total = db.execute(select(func.count()).select_from(statement.subquery())).scalar_one()
    rows = db.execute(
        statement.order_by(Order.created_at.desc(), Order.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    order_ids = [row.Order.id for row in rows]
    active_refunds = _active_refunds_by_order_ids(db, order_ids)
    order_summaries = _order_summaries_by_order_ids(db, order_ids)
    return OrderListResponse(
        items=[
            _order_to_public(
                row,
                active_refunds.get(row.Order.id),
                order_summaries.get(row.Order.id),
            )
            for row in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


def get_order_detail(db: Any, user: Any, order_id: int) -> OrderDetail:
    _expire_overdue_wait_pay_orders(db, user)
    _escalate_overdue_refunds(db, user=user)
    statement = _order_query_for_user(user).where(Order.id == order_id)
    row = db.execute(statement).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    return _order_to_detail(db, row, _order_item_rows(db, order_id))


def _get_order_for_update(db: Any, order_id: int) -> Order:
    order = db.execute(
        select(Order)
        .where(Order.id == order_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    return order


def _pay_locked_order(db: Any, buyer: Any, order: Order, *, allow_partial: bool = False) -> None:
    if order.status == OrderStatus.WAIT_PAY and _payment_deadline_reached(order.payment_expires_at, datetime.now(UTC)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order payment window has expired.")
    if order.status != OrderStatus.WAIT_PAY:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only wait-pay orders can be paid.")
    if not _order_item_rows(db, order.id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order has no items.")
    _ensure_order_seller_can_receive_payment(db, order)
    before_status = order.status
    try:
        _freeze_wallet_amount(
            db,
            buyer.id,
            order.payable_amount,
            reference_type="order_pay",
            reference_id=order.id,
            allow_partial=allow_partial,
        )
        order.status = OrderStatus.PAID
        order.paid_at = datetime.now(UTC)
        _write_order_status_log(
            db,
            order,
            from_status=before_status,
            to_status=OrderStatus.PAID,
            operator_id=buyer.id,
            note="Buyer paid order and wallet amount frozen.",
        )
    except HTTPException:
        if allow_partial:
            _release_order_locked_stock(db, order)
            order.status = OrderStatus.CANCELLED
            _write_order_status_log(
                db,
                order,
                from_status=before_status,
                to_status=OrderStatus.CANCELLED,
                operator_id=buyer.id,
                note="Auto-pay failed; order cancelled and locked stock released.",
            )
        raise


def _release_order_locked_stock(db: Any, order: Order) -> None:
    order_items = sorted(_order_item_rows(db, order.id), key=lambda item: item.sku_id)
    for item in order_items:
        sku = _lock_sku(db, item.sku_id)
        if sku.stock_locked < item.quantity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid locked stock state.")
        sku.stock_locked -= item.quantity
        sku.stock_available += item.quantity
        sku.version += 1


def pay_order(db: Any, buyer: Any, order_id: int) -> OrderDetail:
    _ensure_buyer(buyer)
    order = _get_order_for_update(db, order_id)
    if order.buyer_id != buyer.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    if _expire_wait_pay_order_locked(db, order):
        db.flush()
        return get_order_detail(db, buyer, order.id)
    if order.status == OrderStatus.PAID:
        return get_order_detail(db, buyer, order.id)
    if order.status != OrderStatus.WAIT_PAY:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only wait-pay orders can be paid.")
    _pay_locked_order(db, buyer, order)
    db.flush()
    return get_order_detail(db, buyer, order.id)


def cancel_order(db: Any, buyer: Any, order_id: int) -> OrderDetail:
    _ensure_buyer(buyer)
    order = _get_order_for_update(db, order_id)
    if order.buyer_id != buyer.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    if _expire_wait_pay_order_locked(db, order):
        db.flush()
        return get_order_detail(db, buyer, order.id)
    if order.status not in {OrderStatus.WAIT_PAY, OrderStatus.PAID} or order.is_shipped:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only unshipped wait-pay or paid orders can be cancelled.",
        )
    before_status = order.status
    _release_order_locked_stock(db, order)
    if before_status == OrderStatus.PAID:
        _refund_frozen_amount(
            db,
            buyer.id,
            order.payable_amount,
            reference_type="order_cancel",
            reference_id=order.id,
        )
    order.status = OrderStatus.CANCELLED
    _write_order_status_log(
        db,
        order,
        from_status=before_status,
        to_status=OrderStatus.CANCELLED,
        operator_id=buyer.id,
        note="Buyer cancelled order; locked stock released.",
    )
    db.flush()
    return get_order_detail(db, buyer, order.id)


def ship_order(db: Any, seller: Any, order_id: int) -> OrderDetail:
    merchant = _ensure_seller_merchant(seller)
    order = _get_order_for_update(db, order_id)
    if order.seller_id != merchant.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    if order.status != OrderStatus.PAID or order.is_shipped:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only unshipped paid orders can be shipped.")
    before_status = order.status
    order.status = OrderStatus.SHIPPED
    order.is_shipped = True
    order.shipped_at = datetime.now(UTC)
    _write_order_status_log(
        db,
        order,
        from_status=before_status,
        to_status=OrderStatus.SHIPPED,
        operator_id=seller.id,
        note="Seller shipped order.",
    )
    db.flush()
    return get_order_detail(db, seller, order.id)


def complete_order(db: Any, buyer: Any, order_id: int) -> OrderDetail:
    _ensure_buyer(buyer)
    order = _get_order_for_update(db, order_id)
    if order.buyer_id != buyer.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    if order.status != OrderStatus.SHIPPED or not order.is_shipped:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only shipped orders can be completed.")
    before_status = order.status
    order_items = sorted(_order_item_rows(db, order.id), key=lambda item: item.sku_id)
    if not order_items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order has no items.")
    for item in order_items:
        sku = _lock_sku(db, item.sku_id)
        if sku.stock_locked < item.quantity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid locked stock state.")
        sku.stock_locked -= item.quantity
        sku.version += 1
    _settle_frozen_amount(
        db,
        buyer.id,
        order.payable_amount,
        reference_type="order_complete",
        reference_id=order.id,
    )
    merchant = db.get(MerchantProfile, order.seller_id)
    if merchant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Merchant profile not found.")
    _settle_seller_income(
        db,
        merchant.user_id,
        order.payable_amount,
        reference_type="order_complete",
        reference_id=order.id,
    )
    order.status = OrderStatus.COMPLETED
    _write_order_status_log(
        db,
        order,
        from_status=before_status,
        to_status=OrderStatus.COMPLETED,
        operator_id=buyer.id,
        note="Buyer confirmed receipt and funds settled.",
    )
    db.flush()
    return get_order_detail(db, buyer, order.id)


def create_refund_application(
    db: Any,
    buyer: Any,
    *,
    order_id: int,
    reason: str,
    description: str | None,
    amount: Decimal | None,
    evidence_images_json: list[str] | None,
) -> RefundApplication:
    _ensure_buyer(buyer)
    _escalate_overdue_refunds(db, user=buyer)
    order = _get_order_for_update(db, order_id)
    if order.buyer_id != buyer.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    if not order.is_shipped or order.status not in {OrderStatus.SHIPPED, OrderStatus.COMPLETED}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only shipped or completed orders can request refund.",
        )
    refund_amount = amount or order.payable_amount
    if refund_amount != order.payable_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only full-order refunds are supported in the first version.",
        )
    existing = db.execute(
        select(RefundApplication).where(
            RefundApplication.order_id == order.id,
            RefundApplication.status.in_(ACTIVE_REFUND_STATUSES),
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order already has an active refund.")

    refund = RefundApplication(
        order_id=order.id,
        order_item_id=None,
        buyer_id=buyer.id,
        seller_id=order.seller_id,
        status=RefundStatus.PENDING,
        reason=reason,
        description=description,
        amount=refund_amount,
        evidence_images_json=evidence_images_json,
        admin_note=None,
        seller_deadline_at=datetime.now(UTC) + timedelta(days=REFUND_SELLER_RESPONSE_DAYS),
        seller_handled_at=None,
        seller_note=None,
        seller_handler_id=None,
    )
    db.add(refund)
    db.flush()
    return refund


def _refund_to_public(refund: RefundApplication) -> RefundPublic:
    return RefundPublic(
        id=refund.id,
        order_id=refund.order_id,
        order_item_id=refund.order_item_id,
        buyer_id=refund.buyer_id,
        seller_id=refund.seller_id,
        status=refund.status,
        reason=refund.reason,
        description=refund.description,
        amount=refund.amount,
        evidence_images_json=refund.evidence_images_json,
        admin_note=refund.admin_note,
        seller_deadline_at=refund.seller_deadline_at,
        seller_handled_at=refund.seller_handled_at,
        seller_note=refund.seller_note,
        seller_handler_id=refund.seller_handler_id,
        created_at=refund.created_at,
        updated_at=refund.updated_at,
    )


def list_refunds(
    db: Any,
    user: Any,
    *,
    status_filter: RefundStatus | None = None,
    page: int = 1,
    page_size: int = 20,
) -> RefundListResponse:
    _escalate_overdue_refunds(db, user=user)
    statement = select(RefundApplication)
    role = _role_value(user)
    if role == UserRole.BUYER.value:
        statement = statement.where(RefundApplication.buyer_id == user.id)
    elif role == UserRole.SELLER.value:
        merchant = _ensure_seller_merchant(user)
        statement = statement.where(RefundApplication.seller_id == merchant.id)
    elif role != UserRole.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unsupported role.")
    if status_filter is not None:
        statement = statement.where(RefundApplication.status == status_filter)
    total = db.execute(select(func.count()).select_from(statement.subquery())).scalar_one()
    items = db.execute(
        statement.order_by(RefundApplication.created_at.desc(), RefundApplication.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()
    return RefundListResponse(
        items=[_refund_to_public(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


def review_refund(
    db: Any,
    admin: Any,
    refund_id: int,
    *,
    approved: bool,
    admin_note: str | None = None,
) -> RefundPublic:
    _ensure_admin(admin)
    _escalate_overdue_refunds(db, user=admin, refund_id=refund_id)
    refund = db.execute(
        select(RefundApplication)
        .where(RefundApplication.id == refund_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if refund is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refund not found.")
    if refund.status != RefundStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Refund is not pending.")
    order = _get_order_for_update(db, refund.order_id)
    refund.admin_note = admin_note

    if approved:
        _complete_refund_locked(
            db,
            refund,
            order,
            reference_type="refund",
            reference_id=refund.id,
            operator_id=admin.id,
            note="Admin approved refund.",
        )
    else:
        refund.status = RefundStatus.REJECTED
    db.flush()
    return _refund_to_public(refund)


def review_seller_refund(
    db: Any,
    seller: Any,
    refund_id: int,
    *,
    approved: bool,
    seller_note: str | None = None,
) -> RefundPublic:
    merchant = _ensure_seller_merchant(seller)
    refund = db.execute(
        select(RefundApplication)
        .where(RefundApplication.id == refund_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if refund is None or refund.seller_id != merchant.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refund not found.")
    if refund.status != RefundStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Refund is not pending.")

    now = datetime.now(UTC)
    if _refund_deadline_reached(refund.seller_deadline_at, now):
        order = _get_order_for_update(db, refund.order_id)
        _create_refund_dispute_locked(
            db,
            refund,
            order,
            initiator_id=refund.buyer_id,
            initiator_role=UserRole.BUYER,
            reason="Seller response timed out.",
            description="Seller did not handle the refund request within 3 days.",
            evidence_images_json=None,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seller response deadline has expired; refund was escalated to dispute.",
        )

    order = _get_order_for_update(db, refund.order_id)
    refund.seller_note = seller_note
    refund.seller_handler_id = seller.id
    refund.seller_handled_at = now

    if approved:
        _complete_refund_locked(
            db,
            refund,
            order,
            reference_type="refund",
            reference_id=refund.id,
            operator_id=seller.id,
            note="Seller approved refund.",
        )
    else:
        refund.status = RefundStatus.REJECTED
    db.flush()
    return _refund_to_public(refund)


def create_product_review(
    db: Any,
    buyer: Any,
    *,
    order_item_id: int,
    rating: int,
    content: str | None,
    images_json: list[str] | None,
) -> ReviewPublic:
    _ensure_buyer(buyer)
    row = db.execute(
        select(OrderItem, Order)
        .join(Order, OrderItem.order_id == Order.id)
        .where(OrderItem.id == order_item_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if row is None or row.Order.buyer_id != buyer.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order item not found.")
    if row.Order.status != OrderStatus.COMPLETED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only completed orders can be reviewed.")
    existing = db.execute(
        select(ProductReview).where(ProductReview.order_item_id == order_item_id)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order item already reviewed.")

    review = ProductReview(
        user_id=buyer.id,
        order_item_id=row.OrderItem.id,
        spu_id=row.OrderItem.spu_id,
        sku_id=row.OrderItem.sku_id,
        rating=rating,
        content=content,
        images_json=images_json,
        seller_reply=None,
    )
    db.add(review)
    db.flush()
    return ReviewPublic.model_validate(review)


def list_reviews(
    db: Any,
    *,
    user: Any | None = None,
    spu_id: int | None = None,
    public_only: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> ReviewListResponse:
    statement = select(ProductReview)
    if user is not None:
        role = _role_value(user)
        if role == UserRole.BUYER.value:
            statement = statement.where(ProductReview.user_id == user.id)
        elif role == UserRole.SELLER.value:
            merchant = _ensure_seller_merchant(user)
            statement = statement.join(ProductSpu, ProductReview.spu_id == ProductSpu.id).where(
                ProductSpu.merchant_id == merchant.id
            )
        elif role != UserRole.ADMIN.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unsupported role.")
    if spu_id is not None:
        statement = statement.where(ProductReview.spu_id == spu_id)
    if public_only:
        statement = statement.where(ProductReview.status == ReviewStatus.VISIBLE)
    total = db.execute(select(func.count()).select_from(statement.subquery())).scalar_one()
    reviews = db.execute(
        statement.order_by(ProductReview.created_at.desc(), ProductReview.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()
    review_items = _review_public_items(db, reviews)
    return ReviewListResponse(
        items=review_items,
        total=total,
        page=page,
        page_size=page_size,
    )


def list_review_products(
    db: Any,
    seller: Any,
    *,
    page: int = 1,
    page_size: int = 20,
) -> ReviewProductListResponse:
    merchant = _ensure_seller_merchant(seller)
    base = (
        select(ProductReview.spu_id)
        .join(ProductSpu, ProductReview.spu_id == ProductSpu.id)
        .where(ProductSpu.merchant_id == merchant.id)
        .group_by(ProductReview.spu_id)
        .subquery()
    )
    total = db.execute(select(func.count()).select_from(base)).scalar_one()

    pending_count_expr = func.sum(case((ProductReview.seller_reply.is_(None), 1), else_=0))
    latest_review_expr = func.max(ProductReview.created_at)
    statement = (
        select(
            ProductReview.spu_id,
            ProductSpu.name.label("product_name"),
            ProductSpu.cover_image_url.label("product_cover_image_url"),
            func.count(ProductReview.id).label("review_count"),
            pending_count_expr.label("pending_reply_count"),
            latest_review_expr.label("latest_review_at"),
        )
        .join(ProductSpu, ProductReview.spu_id == ProductSpu.id)
        .where(ProductSpu.merchant_id == merchant.id)
        .group_by(ProductReview.spu_id, ProductSpu.name, ProductSpu.cover_image_url)
        .order_by(pending_count_expr.desc(), latest_review_expr.desc(), ProductReview.spu_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = db.execute(statement).all()
    return ReviewProductListResponse(
        items=[
            ReviewProductSummary(
                spu_id=row.spu_id,
                product_name=row.product_name,
                product_cover_image_url=row.product_cover_image_url,
                review_count=row.review_count,
                pending_reply_count=row.pending_reply_count or 0,
                latest_review_at=row.latest_review_at,
            )
            for row in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


def _review_public_items(db: Any, reviews: Sequence[ProductReview]) -> list[ReviewPublic]:
    if not reviews:
        return []
    user_ids = {review.user_id for review in reviews}
    spu_ids = {review.spu_id for review in reviews}
    sku_ids = {review.sku_id for review in reviews}
    users = {
        user.id: user
        for user in db.execute(select(UserAccount).where(UserAccount.id.in_(user_ids))).scalars().all()
    }
    products = {
        product.id: product
        for product in db.execute(select(ProductSpu).where(ProductSpu.id.in_(spu_ids))).scalars().all()
    }
    skus = {
        sku.id: sku
        for sku in db.execute(select(ProductSku).where(ProductSku.id.in_(sku_ids))).scalars().all()
    }
    items: list[ReviewPublic] = []
    for review in reviews:
        product = products.get(review.spu_id)
        sku = skus.get(review.sku_id)
        user_account = users.get(review.user_id)
        items.append(
            ReviewPublic.model_validate(review).model_copy(
                update={
                    "buyer_username": user_account.username if user_account else None,
                    "product_name": product.name if product else None,
                    "product_cover_image_url": product.cover_image_url if product else None,
                    "sku_spec_name": sku.spec_name if sku else None,
                    "sku_unit": sku.unit if sku else None,
                    "sku_spec_attrs_json": sku.spec_attrs_json if sku else None,
                }
            )
        )
    return items


def reply_product_review(
    db: Any,
    seller: Any,
    *,
    review_id: int,
    seller_reply: str,
) -> ReviewPublic:
    merchant = _ensure_seller_merchant(seller)
    review = db.get(ProductReview, review_id)
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found.")
    spu = db.get(ProductSpu, review.spu_id)
    if spu is None or spu.merchant_id != merchant.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found.")
    review.seller_reply = seller_reply
    db.flush()
    return _review_public_items(db, [review])[0]


def delete_product_review_reply(db: Any, seller: Any, *, review_id: int) -> ReviewPublic:
    merchant = _ensure_seller_merchant(seller)
    review = db.get(ProductReview, review_id)
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found.")
    spu = db.get(ProductSpu, review.spu_id)
    if spu is None or spu.merchant_id != merchant.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found.")
    review.seller_reply = None
    db.flush()
    return _review_public_items(db, [review])[0]


def create_refund_dispute(
    db: Any,
    user: Any,
    *,
    refund_id: int,
    reason: str,
    description: str | None,
    evidence_images_json: list[str] | None,
) -> DisputePublic:
    _ensure_buyer(user)
    refund = db.execute(
        select(RefundApplication)
        .where(RefundApplication.id == refund_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if refund is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refund not found.")
    if refund.buyer_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refund not found.")

    existing = db.execute(
        select(RefundDispute.id).where(RefundDispute.refund_id == refund.id).limit(1)
    ).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Refund already has a dispute record.")

    order = _get_order_for_update(db, refund.order_id)
    if order.status not in {OrderStatus.SHIPPED, OrderStatus.COMPLETED}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refund order is not in a disputable state.",
        )

    if refund.status == RefundStatus.PENDING:
        if not _refund_deadline_reached(refund.seller_deadline_at, datetime.now(UTC)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pending refunds can only be disputed after seller response deadline.",
            )
        dispute = _create_refund_dispute_locked(
            db,
            refund,
            order,
            initiator_id=user.id,
            initiator_role=UserRole.BUYER,
            reason="Seller response timed out.",
            description=description or "Seller did not handle the refund request within 3 days.",
            evidence_images_json=evidence_images_json,
        )
    elif refund.status == RefundStatus.REJECTED:
        dispute = _create_refund_dispute_locked(
            db,
            refund,
            order,
            initiator_id=user.id,
            initiator_role=UserRole.BUYER,
            reason=reason,
            description=description,
            evidence_images_json=evidence_images_json,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only rejected or overdue pending refunds can be disputed.",
        )
    db.flush()
    return DisputePublic.model_validate(dispute)


def list_refund_disputes(
    db: Any,
    user: Any,
    *,
    status_filter: DisputeStatus | None = None,
    page: int = 1,
    page_size: int = 20,
) -> DisputeListResponse:
    _escalate_overdue_refunds(db, user=user)
    statement = select(RefundDispute)
    role = _role_value(user)
    if role == UserRole.BUYER.value:
        statement = statement.where(RefundDispute.buyer_id == user.id)
    elif role == UserRole.SELLER.value:
        merchant = _ensure_seller_merchant(user)
        statement = statement.where(RefundDispute.seller_id == merchant.id)
    elif role != UserRole.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unsupported role.")
    if status_filter is not None:
        statement = statement.where(RefundDispute.status == status_filter)
    total = db.execute(select(func.count()).select_from(statement.subquery())).scalar_one()
    disputes = db.execute(
        statement.order_by(RefundDispute.created_at.desc(), RefundDispute.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()
    return DisputeListResponse(
        items=[DisputePublic.model_validate(dispute) for dispute in disputes],
        total=total,
        page=page,
        page_size=page_size,
    )


def review_refund_dispute(
    db: Any,
    admin: Any,
    *,
    dispute_id: int,
    approved: bool,
    resolution_note: str | None = None,
) -> DisputePublic:
    _ensure_admin(admin)
    dispute = db.execute(
        select(RefundDispute)
        .where(RefundDispute.id == dispute_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if dispute is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispute not found.")
    if dispute.status != DisputeStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Dispute is not pending.")
    refund = db.execute(
        select(RefundApplication)
        .where(RefundApplication.id == dispute.refund_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if refund is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refund not found.")
    order = _get_order_for_update(db, dispute.order_id)
    if refund.status != RefundStatus.DISPUTED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Refund dispute state is inconsistent.")

    dispute.status = DisputeStatus.APPROVED if approved else DisputeStatus.REJECTED
    dispute.resolution_note = resolution_note
    dispute.resolved_by = admin.id
    dispute.resolved_at = datetime.now(UTC)

    if approved:
        _complete_refund_locked(
            db,
            refund,
            order,
            reference_type="refund_dispute",
            reference_id=dispute.id,
            operator_id=admin.id,
            note="Admin approved refund dispute; refund completed.",
        )
    else:
        refund.status = RefundStatus.REJECTED
    db.flush()
    return DisputePublic.model_validate(dispute)
