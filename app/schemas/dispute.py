from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DisputeStatus, UserRole


class DisputeCreate(BaseModel):
    refund_id: int
    reason: str = Field(min_length=1, max_length=255)
    description: str | None = None
    evidence_images_json: list[str] | None = None


class DisputeDecision(BaseModel):
    resolution_note: str | None = Field(default=None, max_length=500)


class DisputePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    refund_id: int
    order_id: int
    buyer_id: int
    seller_id: int
    initiator_id: int
    initiator_role: UserRole
    status: DisputeStatus
    reason: str
    description: str | None = None
    evidence_images_json: list[str] | None = None
    resolution_note: str | None = None
    resolved_by: int | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class DisputeListResponse(BaseModel):
    items: list[DisputePublic]
    total: int
    page: int
    page_size: int
