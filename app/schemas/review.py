from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ReviewStatus


class ReviewCreate(BaseModel):
    order_item_id: int
    rating: int = Field(ge=1, le=5)
    content: str | None = Field(default=None, max_length=1000)
    images_json: list[str] | None = None


class ReviewReply(BaseModel):
    seller_reply: str = Field(min_length=1, max_length=1000)


class ReviewPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    order_item_id: int
    spu_id: int
    sku_id: int
    rating: int
    content: str | None = None
    images_json: list[str] | None = None
    seller_reply: str | None = None
    status: ReviewStatus
    buyer_username: str | None = None
    product_name: str | None = None
    product_cover_image_url: str | None = None
    sku_spec_name: str | None = None
    sku_unit: str | None = None
    sku_spec_attrs_json: dict | None = None
    created_at: datetime
    updated_at: datetime


class ReviewListResponse(BaseModel):
    items: list[ReviewPublic]
    total: int
    page: int
    page_size: int


class ReviewProductSummary(BaseModel):
    spu_id: int
    product_name: str
    product_cover_image_url: str | None = None
    review_count: int
    pending_reply_count: int
    latest_review_at: datetime | None = None


class ReviewProductListResponse(BaseModel):
    items: list[ReviewProductSummary]
    total: int
    page: int
    page_size: int
