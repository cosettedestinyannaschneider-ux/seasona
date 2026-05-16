from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import OrderStatus, PaymentStatus, RefundStatus
from app.schemas.review import ReviewPublic


class ReceiverSnapshot(BaseModel):
    receiver_name: str = Field(min_length=1, max_length=64)
    receiver_phone: str = Field(min_length=1, max_length=32)
    province: str = Field(min_length=1, max_length=64)
    city: str = Field(default="", max_length=64)
    district: str = Field(min_length=1, max_length=64)
    detail: str = Field(min_length=1, max_length=255)

    @model_validator(mode="after")
    def validate_city_for_regular_province(self) -> "ReceiverSnapshot":
        province_level_regions = {"北京市", "天津市", "上海市", "重庆市", "香港特别行政区", "澳门特别行政区"}
        if self.province not in province_level_regions and not self.city:
            raise ValueError("city is required.")
        return self


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
    payment_id: int | None = None
    primary_product_name: str | None = None
    item_count: int = 0
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


class CheckoutPaymentPublic(BaseModel):
    id: int
    payment_no: str
    buyer_id: int
    status: PaymentStatus
    total_amount: Decimal
    freight_amount: Decimal
    payable_amount: Decimal
    receiver_snapshot_json: dict
    payment_expires_at: datetime
    paid_at: datetime | None = None
    cancelled_at: datetime | None = None
    expired_at: datetime | None = None
    primary_product_name: str | None = None
    item_count: int = 0
    order_count: int = 0
    created_at: datetime
    updated_at: datetime


class CheckoutPaymentDetail(CheckoutPaymentPublic):
    orders: list[OrderDetail]


class CheckoutPaymentListResponse(BaseModel):
    items: list[CheckoutPaymentDetail]
    total: int
    page: int
    page_size: int


class OrderCreateResponse(BaseModel):
    orders: list[OrderDetail]
    payment: CheckoutPaymentDetail | None = None
