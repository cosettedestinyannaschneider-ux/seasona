from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.enums import OrderStatus, RefundStatus, WalletBizType
from app.models.order import Cart, CartItem, Order, RefundApplication, RefundDispute
from app.models.wallet import WalletAccount, WalletLedger
from app.services.commerce import service as commerce_service
from test.factories import (
    WalletRechargeRequestFactory,
    create_buyer,
    create_paid_order,
    create_product,
    create_seller,
    receiver_snapshot,
)


pytestmark = pytest.mark.integration


def test_recharge_wallet_is_idempotent_and_writes_one_ledger(db_session) -> None:
    buyer = create_buyer(db_session)

    payload = WalletRechargeRequestFactory.build()

    commerce_service.recharge_wallet(db_session, buyer, payload.amount, payload.idempotency_key)
    commerce_service.recharge_wallet(db_session, buyer, payload.amount, payload.idempotency_key)

    wallet = db_session.execute(select(WalletAccount).where(WalletAccount.user_id == buyer.id)).scalar_one()
    ledgers = db_session.execute(select(WalletLedger).where(WalletLedger.wallet_account_id == wallet.id)).scalars().all()
    assert wallet.available_balance == Decimal("100.00")
    assert len(ledgers) == 1
    assert ledgers[0].biz_type == WalletBizType.RECHARGE


def test_cart_order_payment_cancel_and_stock_release_flow(db_session) -> None:
    buyer = create_buyer(db_session)
    seller = create_seller(db_session)
    _, sku = create_product(db_session, seller, stock=5, price="8.80")
    cart = db_session.execute(select(Cart).where(Cart.buyer_id == buyer.id)).scalar_one()
    db_session.add(CartItem(cart_id=cart.id, sku_id=sku.id, quantity=2, selected=True))
    db_session.flush()

    orders, payment = commerce_service.create_orders_from_cart(
        db_session,
        buyer,
        receiver_snapshot=receiver_snapshot(),
        idempotency_key="checkout-001",
    )

    assert payment is not None
    assert len(orders) == 1
    db_session.refresh(sku)
    assert sku.stock_available == 3
    assert sku.stock_locked == 2

    commerce_service.recharge_wallet(db_session, buyer, Decimal("20.00"), "recharge-002")
    paid = commerce_service.pay_checkout_payment(db_session, buyer, payment.id)
    db_session.refresh(sku)
    assert paid.status.value == "PAID"
    assert paid.orders[0].status == OrderStatus.PAID

    cancelled = commerce_service.cancel_order(db_session, buyer, paid.orders[0].id)
    db_session.refresh(sku)
    wallet = db_session.execute(select(WalletAccount).where(WalletAccount.user_id == buyer.id)).scalar_one()
    assert cancelled.status == OrderStatus.CANCELLED
    assert sku.stock_available == 5
    assert sku.stock_locked == 0
    assert wallet.available_balance == Decimal("20.00")
    assert wallet.frozen_balance == Decimal("0.00")


def test_ship_complete_settles_buyer_frozen_funds_to_seller(db_session) -> None:
    buyer = create_buyer(db_session)
    seller = create_seller(db_session)
    _, sku = create_product(db_session, seller, stock=2, price="8.80")
    commerce_service.recharge_wallet(db_session, buyer, Decimal("20.00"), "recharge-003")

    order_detail = commerce_service.create_order_from_sku(
        db_session,
        buyer,
        receiver_snapshot=receiver_snapshot(),
        idempotency_key="direct-001",
        sku_id=sku.id,
        quantity=1,
    )
    commerce_service.pay_checkout_payment(db_session, buyer, order_detail.payment_id)
    shipped = commerce_service.ship_order(db_session, seller, order_detail.id)
    completed = commerce_service.complete_order(db_session, buyer, shipped.id)

    buyer_wallet = db_session.execute(select(WalletAccount).where(WalletAccount.user_id == buyer.id)).scalar_one()
    seller_wallet = db_session.execute(select(WalletAccount).where(WalletAccount.user_id == seller.id)).scalar_one()
    assert completed.status == OrderStatus.COMPLETED
    assert buyer_wallet.available_balance == Decimal("11.20")
    assert buyer_wallet.frozen_balance == Decimal("0.00")
    assert seller_wallet.available_balance == Decimal("8.80")


def test_refund_paths_for_shipped_completed_and_overdue_dispute(db_session) -> None:
    buyer = create_buyer(db_session)
    seller = create_seller(db_session)
    commerce_service.recharge_wallet(db_session, buyer, Decimal("100.00"), "recharge-004")
    shipped_order = create_paid_order(db_session, buyer, seller, shipped=True)
    buyer_wallet = db_session.execute(select(WalletAccount).where(WalletAccount.user_id == buyer.id)).scalar_one()
    buyer_wallet.available_balance = Decimal("91.20")
    buyer_wallet.frozen_balance = Decimal("8.80")
    db_session.flush()

    refund = commerce_service.create_refund_application(
        db_session,
        buyer,
        order_id=shipped_order.id,
        reason="bad",
        description=None,
        amount=None,
        evidence_images_json=[],
    )
    completed_refund = commerce_service.review_seller_refund(db_session, seller, refund.id, approved=True)
    db_session.refresh(shipped_order)
    db_session.refresh(buyer_wallet)
    assert completed_refund.status == RefundStatus.COMPLETED
    assert shipped_order.status == OrderStatus.REFUNDED
    assert buyer_wallet.available_balance == Decimal("100.00")
    assert buyer_wallet.frozen_balance == Decimal("0.00")

    completed_order = create_paid_order(db_session, buyer, seller, completed=True)
    seller_wallet = db_session.execute(select(WalletAccount).where(WalletAccount.user_id == seller.id)).scalar_one()
    seller_wallet.available_balance = Decimal("8.80")
    db_session.flush()
    refund2 = commerce_service.create_refund_application(
        db_session,
        buyer,
        order_id=completed_order.id,
        reason="bad",
        description=None,
        amount=None,
        evidence_images_json=[],
    )
    commerce_service.review_seller_refund(db_session, seller, refund2.id, approved=True)
    db_session.refresh(seller_wallet)
    assert seller_wallet.available_balance == Decimal("0.00")

    overdue_order = create_paid_order(db_session, buyer, seller, shipped=True)
    refund3 = commerce_service.create_refund_application(
        db_session,
        buyer,
        order_id=overdue_order.id,
        reason="timeout",
        description=None,
        amount=None,
        evidence_images_json=[],
    )
    db_session.get(RefundApplication, refund3.id).seller_deadline_at = datetime.now(UTC) - timedelta(days=1)
    dispute = commerce_service.create_refund_dispute(
        db_session,
        buyer,
        refund_id=refund3.id,
        reason="timeout",
        description=None,
        evidence_images_json=[],
    )
    assert dispute.status.value == "pending"
    assert db_session.execute(select(RefundDispute).where(RefundDispute.refund_id == refund3.id)).scalar_one()


def test_review_draft_publish_like_comment_and_reply_flow(db_session) -> None:
    buyer = create_buyer(db_session)
    seller = create_seller(db_session)
    order = create_paid_order(db_session, buyer, seller, completed=True)
    item = commerce_service._order_item_rows(db_session, order.id)[0]

    draft = commerce_service.save_product_review_draft(
        db_session,
        buyer,
        spu_id=item.spu_id,
        order_id=order.id,
        order_item_id=item.id,
        rating=4,
        content="draft",
        images_json=[],
    )
    assert draft.status.value == "pending"

    review = commerce_service.create_product_review(
        db_session,
        buyer,
        spu_id=item.spu_id,
        order_id=order.id,
        order_item_id=item.id,
        rating=5,
        content="good",
        images_json=[],
    )
    assert review.status.value == "visible"

    with pytest.raises(HTTPException) as duplicate:
        commerce_service.create_product_review(
            db_session,
            buyer,
            spu_id=item.spu_id,
            order_id=order.id,
            order_item_id=item.id,
            rating=5,
            content="again",
            images_json=[],
        )
    assert duplicate.value.status_code == 409

    liked = commerce_service.like_product_review(db_session, buyer, review_id=review.id)
    assert liked.viewer_liked is True
    detail = commerce_service.create_review_comment(db_session, buyer, review_id=review.id, parent_id=None, content="comment")
    assert detail.comment_count == 1
    replied = commerce_service.reply_product_review(db_session, seller, review_id=review.id, seller_reply="thanks")
    assert replied.has_seller_reply is True
