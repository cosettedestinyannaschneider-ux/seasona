from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class ProductSearchSort(StrEnum):
    RELEVANCE = "relevance"
    NEWEST = "newest"
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"
    STOCK_DESC = "stock_desc"


class ProductSearchSource(StrEnum):
    MEILISEARCH = "meilisearch"


class ProductSearchSku(BaseModel):
    sku_id: int
    spec_name: str
    unit: str
    price: Decimal
    original_price: Decimal | None = None
    stock_available: int
    stock_locked: int


class ProductSearchCard(BaseModel):
    spu_id: int
    name: str
    description: str | None = None
    origin_place: str | None = None
    cover_image_url: str | None = None
    merchant_id: int
    merchant_shop_name: str | None = None
    category_id: int
    category_name: str | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    stock_total: int = 0
    average_rating: float | None = None
    review_count: int = 0
    default_sku_id: int | None = None
    default_sku_unit: str | None = None
    skus: list[ProductSearchSku] = Field(default_factory=list)
    score: float | None = None
    match_source: str | None = None
    match_sources: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProductSearchResponse(BaseModel):
    items: list[ProductSearchCard]
    total: int
    page: int
    page_size: int
    query: str = ""
    source: ProductSearchSource


class SearchReindexResponse(BaseModel):
    index_name: str
    total: int
    indexed: int
    task_uids: list[int] = Field(default_factory=list)
