from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ReviewStatus


class ReviewCreate(BaseModel):
    order_id: int | None = None
    order_item_id: int | None = None
    rating: int = Field(ge=1, le=5)
    content: str | None = Field(default=None, max_length=3000)
    images_json: list[str] | None = Field(default=None, max_length=9)


class ReviewDraftUpsert(BaseModel):
    order_id: int | None = None
    order_item_id: int | None = None
    rating: int | None = Field(default=None, ge=1, le=5)
    content: str | None = Field(default=None, max_length=3000)
    images_json: list[str] | None = Field(default=None, max_length=9)


class ReviewReply(BaseModel):
    seller_reply: str = Field(min_length=1, max_length=1000)


class ReviewCommentCreate(BaseModel):
    parent_id: int | None = None
    content: str = Field(min_length=1, max_length=1000)


class ReviewCommentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    review_id: int
    parent_id: int | None = None
    user_id: int | None = None
    author_role: Literal["buyer", "seller", "admin"]
    content: str
    reply_to_name: str | None = None
    author_username: str | None = None
    author_nickname: str | None = None
    author_avatar_url: str | None = None
    can_delete: bool = False
    created_at: datetime
    updated_at: datetime


class ReviewPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    order_id: int | None = None
    order_item_id: int | None = None
    spu_id: int
    sku_id: int | None = None
    rating: int | None = None
    content: str | None = None
    images_json: list[str] | None = None
    seller_reply: str | None = None
    status: ReviewStatus
    buyer_username: str | None = None
    buyer_nickname: str | None = None
    buyer_avatar_url: str | None = None
    product_name: str | None = None
    product_cover_image_url: str | None = None
    like_count: int = 0
    comment_count: int = 0
    has_seller_reply: bool = False
    viewer_liked: bool = False
    can_delete: bool = False
    created_at: datetime
    updated_at: datetime


class ReviewDetailPublic(ReviewPublic):
    comments: list[ReviewCommentPublic] = Field(default_factory=list)


class ReviewListResponse(BaseModel):
    items: list[ReviewPublic]
    total: int
    page: int
    page_size: int


class ReviewDraftListResponse(BaseModel):
    items: list[ReviewPublic]
    total: int
    page: int
    page_size: int


class ReviewableOrderItem(BaseModel):
    order_id: int
    order_item_id: int | None = None
    order_no: str
    spu_id: int
    order_item_count: int = 1
    quantity: int
    unit_price: Decimal
    completed_at: datetime | None = None
    already_reviewed: bool = False


class ReviewEligibilityResponse(BaseModel):
    can_write_free_review: bool
    free_review_exists: bool
    has_completed_purchase: bool
    reviewable_items: list[ReviewableOrderItem] = Field(default_factory=list)


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
