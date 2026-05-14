from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import OrderStatus, RefundStatus
from app.schemas.review import ReviewPublic


class ReceiverSnapshot(BaseModel):
    receiver_name: str = Field(min_length=1, max_length=64)
    receiver_phone: str = Field(min_length=1, max_length=32)
    province: str = Field(min_length=1, max_length=64)
    city: str = Field(min_length=1, max_length=64)
    district: str = Field(min_length=1, max_length=64)
    detail: str = Field(min_length=1, max_length=255)


class OrderCreate(BaseModel):
    idempotency_key: str = Field(
        min_length=8,
        max_length=80,
        pattern=r"^[A-Za-z0-9.-]+$",
    )
    receiver_snapshot: ReceiverSnapshot
    cart_item_ids: list[int] | None = None
    auto_pay: bool = False


class DirectOrderCreate(BaseModel):
    idempotency_key: str = Field(
        min_length=8,
        max_length=80,
        pattern=r"^[A-Za-z0-9.-]+$",
    )
    receiver_snapshot: ReceiverSnapshot
    sku_id: int
    quantity: int = Field(default=1, ge=1)
    auto_pay: bool = False


class OrderItemPublic(BaseModel):
    id: int
    spu_id: int
    sku_id: int
    product_name_snapshot: str
    spec_name_snapshot: str
    sku_unit: str | None = None
    sku_spec_attrs_json: dict | None = None
    cover_image_url_snapshot: str | None = None
    unit_price: Decimal
    quantity: int
    total_amount: Decimal
    review: ReviewPublic | None = None


class OrderPublic(BaseModel):
    id: int
    order_no: str
    buyer_id: int
    buyer_username: str | None = None
    seller_id: int
    seller_shop_name: str | None = None
    status: OrderStatus
    total_amount: Decimal
    freight_amount: Decimal
    payable_amount: Decimal
    expected_delivery_at: datetime | None = None
    payment_expires_at: datetime | None = None
    paid_at: datetime | None = None
    is_shipped: bool
    shipped_at: datetime | None = None
    active_refund_id: int | None = None
    active_refund_status: RefundStatus | None = None
    created_at: datetime
    updated_at: datetime


class OrderDetail(OrderPublic):
    receiver_snapshot_json: dict
    items: list[OrderItemPublic]


class OrderListResponse(BaseModel):
    items: list[OrderPublic]
    total: int
    page: int
    page_size: int


class OrderCreateResponse(BaseModel):
    orders: list[OrderDetail]
