from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class CartItemCreate(BaseModel):
    sku_id: int
    quantity: int = Field(ge=1)
    selected: bool = True


class CartItemUpdate(BaseModel):
    quantity: int | None = Field(default=None, ge=1)
    selected: bool | None = None


class CartItemPublic(BaseModel):
    id: int
    sku_id: int
    spu_id: int
    merchant_id: int
    merchant_shop_name: str
    product_name: str
    spec_name: str
    spec_attrs_json: dict | None = None
    cover_image_url: str | None = None
    unit: str
    unit_price: Decimal
    quantity: int
    selected: bool
    line_amount: Decimal
    stock_available: int
    stock_locked: int
    available: bool
    created_at: datetime
    updated_at: datetime


class CartPublic(BaseModel):
    id: int
    buyer_id: int
    items: list[CartItemPublic]
    total_quantity: int
    total_amount: Decimal
    selected_amount: Decimal
