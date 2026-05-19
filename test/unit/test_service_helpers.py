from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.models.enums import LedgerDirection, ProductStatus
from app.models.product import ProductCategory, ProductImage, ProductTraceability
from app.schemas.product import ProductImageCreate
from app.services.catalog.service import _image_signature, build_category_tree
from app.services.commerce.service import (
    _payment_deadline_reached,
    _refund_deadline_reached,
    _signed_ledger_amount,
    _split_order_idempotency_key,
    _wallet_recharge_reference_id,
)


pytestmark = pytest.mark.unit


class LedgerStub:
    def __init__(self, direction: LedgerDirection, amount: str) -> None:
        self.direction = direction
        self.amount = Decimal(amount)


def test_deadline_helpers_treat_naive_and_aware_datetimes_consistently() -> None:
    now = datetime(2026, 5, 20, 8, 0, tzinfo=UTC)

    assert _payment_deadline_reached(now - timedelta(seconds=1), now)
    assert _refund_deadline_reached(datetime(2026, 5, 20, 8, 0), now)
    assert not _payment_deadline_reached(now + timedelta(seconds=1), now)
    assert not _refund_deadline_reached(None, now)


def test_idempotency_and_signed_ledger_helpers_are_stable() -> None:
    assert _split_order_idempotency_key("checkout-001", seller_id=7, split_count=1) == "checkout-001"
    assert _split_order_idempotency_key("checkout-001", seller_id=7, split_count=2) == "checkout-001.7"
    assert _wallet_recharge_reference_id("key-1") == _wallet_recharge_reference_id(" key-1 ")

    assert _signed_ledger_amount(LedgerStub(LedgerDirection.IN, "10.00")) == Decimal("10.00")
    assert _signed_ledger_amount(LedgerStub(LedgerDirection.OUT, "10.00")) == Decimal("-10.00")
    assert _signed_ledger_amount(LedgerStub(LedgerDirection.FREEZE, "10.00")) == Decimal("10.00")
    assert _signed_ledger_amount(LedgerStub(LedgerDirection.UNFREEZE, "10.00")) == Decimal("10.00")


def test_category_tree_and_image_signature_are_deterministic() -> None:
    now = datetime(2026, 5, 20, 8, 0, tzinfo=UTC)
    root = ProductCategory(id=1, parent_id=None, name="Root", sort_order=0, is_active=True)
    child = ProductCategory(id=2, parent_id=1, name="Child", sort_order=0, is_active=True)
    root.created_at = root.updated_at = now
    child.created_at = child.updated_at = now

    tree = build_category_tree([root, child])

    assert [node.id for node in tree] == [1]
    assert [node.id for node in tree[0].children] == [2]

    assert _image_signature(ProductImage(image_url="/a.png", sku_id=None, is_cover=True, sort_order=2)) == (
        "/a.png",
        None,
        True,
        2,
    )
    assert _image_signature(ProductImageCreate(image_url="/a.png", is_cover=True, sort_order=2)) == (
        "/a.png",
        None,
        True,
        2,
    )
