from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.search import ProductSearchCard


class AiChatStatus(StrEnum):
    CHAT = "chat"
    REJECT = "reject"
    SUCCESS = "success"


class AiChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    session_id: int | None = None
    candidate_limit: int = Field(default=5, ge=1, le=20)


class AiIngredientMatch(BaseModel):
    ingredient: str
    candidates: list[ProductSearchCard] = Field(default_factory=list)
    missing: bool = False


class AiChatResponse(BaseModel):
    session_id: int
    status: AiChatStatus
    reply: str = ""
    ingredients: list[str] = Field(default_factory=list)
    results: list[AiIngredientMatch] = Field(default_factory=list)
    locked: bool = False
    missing_items: list[str] = Field(default_factory=list)
    has_matches: bool = False


class AiSessionPublic(BaseModel):
    id: int
    buyer_id: int | None = None
    title: str | None = None
    state_json: dict | None = None
    created_at: datetime
    updated_at: datetime


class AiMessagePublic(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    payload_json: dict | None = None
    created_at: datetime
    updated_at: datetime


class AiSessionDetail(AiSessionPublic):
    messages: list[AiMessagePublic] = Field(default_factory=list)
