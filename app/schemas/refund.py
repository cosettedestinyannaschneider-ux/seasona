from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RefundStatus


class RefundCreate(BaseModel):
    order_id: int
    reason: str = Field(min_length=1, max_length=255)
    description: str | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    evidence_images_json: list[str] | None = None


class RefundDecision(BaseModel):
    admin_note: str | None = Field(default=None, max_length=500)


class SellerRefundDecision(BaseModel):
    seller_note: str | None = Field(default=None, max_length=500)


class RefundPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    order_item_id: int | None = None
    buyer_id: int
    seller_id: int
    status: RefundStatus
    reason: str
    description: str | None = None
    amount: Decimal
    evidence_images_json: list[str] | None = None
    admin_note: str | None = None
    seller_deadline_at: datetime | None = None
    seller_handled_at: datetime | None = None
    seller_note: str | None = None
    seller_handler_id: int | None = None
    created_at: datetime
    updated_at: datetime


class RefundListResponse(BaseModel):
    items: list[RefundPublic]
    total: int
    page: int
    page_size: int
