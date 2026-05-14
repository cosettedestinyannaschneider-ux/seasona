from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import LedgerDirection, WalletBizType, WalletStatus


class WalletPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    available_balance: Decimal
    frozen_balance: Decimal
    version: int
    status: WalletStatus
    created_at: datetime
    updated_at: datetime


class WalletRechargeRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    idempotency_key: str = Field(
        min_length=8,
        max_length=80,
        pattern=r"^[A-Za-z0-9.-]+$",
    )


class SellerEarningsPublic(BaseModel):
    wallet: WalletPublic
    merchant_id: int
    total_settled_amount: Decimal
    settled_order_count: int
    pending_settlement_amount: Decimal
    pending_order_count: int
    last_settlement_at: datetime | None = None


class WalletLedgerPublic(BaseModel):
    id: int
    biz_type: WalletBizType
    direction: LedgerDirection
    title: str
    amount: Decimal
    signed_amount: Decimal
    reference_type: str
    reference_id: int
    order_id: int | None = None
    created_at: datetime


class WalletLedgerListResponse(BaseModel):
    items: list[WalletLedgerPublic]
    total: int
    page: int
    page_size: int
