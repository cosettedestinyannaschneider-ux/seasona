from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import ProductStatus, ReviewStatus


class ProductSort(StrEnum):
    NEWEST = "newest"
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"
    STOCK_DESC = "stock_desc"


class CategoryBase(BaseModel):
    parent_id: int | None = None
    name: str = Field(min_length=1, max_length=64)
    sort_order: int = 0
    is_active: bool = True


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    parent_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=64)
    sort_order: int | None = None
    is_active: bool | None = None


class CategoryPublic(CategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class CategoryNode(CategoryPublic):
    children: list["CategoryNode"] = Field(default_factory=list)


class ProductSkuBase(BaseModel):
    spec_name: str = Field(min_length=1, max_length=128)
    spec_attrs_json: dict | None = None
    unit: str = Field(min_length=1, max_length=32)
    price: Decimal = Field(ge=0)
    original_price: Decimal | None = Field(default=None, ge=0)
    stock_available: int = Field(default=0, ge=0)


class ProductSkuCreate(ProductSkuBase):
    pass


class ProductSkuSave(ProductSkuBase):
    id: int | None = None
    version: int | None = Field(default=None, ge=0)


class ProductSkuPublic(ProductSkuBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    spu_id: int
    stock_locked: int
    version: int
    created_at: datetime
    updated_at: datetime


class ProductImageBase(BaseModel):
    image_url: str = Field(min_length=1, max_length=512)
    sku_id: int | None = None
    is_cover: bool = False
    sort_order: int = 0


class ProductImageCreate(ProductImageBase):
    pass


class ProductImagePublic(ProductImageBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    spu_id: int
    created_at: datetime
    updated_at: datetime


class TraceStep(BaseModel):
    title: str = Field(min_length=1, max_length=64)
    content: str = Field(min_length=1, max_length=255)
    happened_at: str | None = Field(default=None, max_length=64)


class ProductTraceabilityBase(BaseModel):
    trace_code: str = Field(min_length=1, max_length=128)
    farm_name: str | None = Field(default=None, max_length=128)
    harvest_date: date | None = None
    inspection_result: str | None = Field(default=None, max_length=128)
    cold_chain_info: str | None = Field(default=None, max_length=255)
    trace_steps_json: list[TraceStep] | None = None


class ProductTraceabilityCreate(ProductTraceabilityBase):
    pass


class ProductTraceabilityPublic(ProductTraceabilityBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    spu_id: int
    created_at: datetime
    updated_at: datetime


class ProductBase(BaseModel):
    category_id: int
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    origin_place: str | None = Field(default=None, max_length=128)
    cover_image_url: str | None = Field(default=None, max_length=512)


class ProductCreate(ProductBase):
    skus: list[ProductSkuCreate] = Field(min_length=1)
    images: list[ProductImageCreate] = Field(default_factory=list)
    traceability: ProductTraceabilityCreate | None = None

    @field_validator("images")
    @classmethod
    def validate_image_count(cls, value: list[ProductImageCreate]) -> list[ProductImageCreate]:
        if len(value) > 12:
            raise ValueError("A product can have at most 12 images.")
        if any(item.sku_id is not None for item in value):
            raise ValueError("SKU-linked product images are not supported.")
        return value


class ProductUpdate(BaseModel):
    category_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    origin_place: str | None = Field(default=None, max_length=128)
    cover_image_url: str | None = Field(default=None, max_length=512)
    images: list[ProductImageCreate] | None = None
    skus: list[ProductSkuSave] | None = Field(default=None, min_length=1)
    traceability: ProductTraceabilityCreate | None = None

    @field_validator("images")
    @classmethod
    def validate_image_count(cls, value: list[ProductImageCreate] | None) -> list[ProductImageCreate] | None:
        if value is not None and len(value) > 12:
            raise ValueError("A product can have at most 12 images.")
        if value is not None and any(item.sku_id is not None for item in value):
            raise ValueError("SKU-linked product images are not supported.")
        return value


class ProductPublic(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    merchant_id: int
    merchant_shop_name: str | None = None
    merchant_shop_logo_url: str | None = None
    category_name: str | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    stock_total: int | None = None
    image_count: int | None = None
    average_rating: float | None = None
    review_count: int = 0
    status: ProductStatus
    review_reason: str | None = None
    reviewed_by: int | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ProductDetail(ProductPublic):
    skus: list[ProductSkuPublic] = Field(default_factory=list)
    images: list[ProductImagePublic] = Field(default_factory=list)
    traceability: ProductTraceabilityPublic | None = None


class ProductListResponse(BaseModel):
    items: list[ProductPublic]
    total: int
    page: int
    page_size: int


class ProductMerchantPublic(BaseModel):
    id: int
    shop_name: str
    shop_logo_url: str | None = None
    shop_description: str | None = None
    product_count: int = 0


class ProductReviewDecision(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class ProductReviewPublic(BaseModel):
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
    created_at: datetime
    updated_at: datetime
