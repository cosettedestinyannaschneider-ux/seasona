from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import MerchantAuditStatus


class MerchantAuditDecision(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class MerchantProfileAdmin(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    shop_name: str
    shop_logo_url: str | None = None
    shop_description: str | None = None
    contact_name: str
    contact_phone: str
    audit_material_text: str | None = None
    audit_images_json: list[str] | None = None
    audit_status: MerchantAuditStatus
    audit_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class MerchantAuditMaterialUpdate(BaseModel):
    audit_material_text: str | None = Field(default=None, max_length=5000)
    audit_images_json: list[str] | None = Field(default=None, max_length=12)

    @field_validator("audit_material_text", mode="before")
    @classmethod
    def normalize_audit_text(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("audit_images_json")
    @classmethod
    def normalize_images(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned: list[str] = []
        for item in value:
            text = str(item).strip()
            if not text:
                continue
            if len(text) > 512:
                raise ValueError("Audit image URL is too long.")
            cleaned.append(text)
        return cleaned


class MerchantProfileUpdate(BaseModel):
    shop_name: str | None = Field(default=None, min_length=1, max_length=128)
    shop_logo_url: str | None = Field(default=None, max_length=512)
    shop_description: str | None = Field(default=None, max_length=5000)

    @field_validator("shop_name", mode="before")
    @classmethod
    def normalize_shop_name(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            raise ValueError("shop_name cannot be empty.")
        return text

    @field_validator("shop_logo_url", "shop_description", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @model_validator(mode="after")
    def validate_shop_name_update(self) -> "MerchantProfileUpdate":
        if "shop_name" in self.model_fields_set and self.shop_name is None:
            raise ValueError("shop_name cannot be null.")
        return self


class MerchantListResponse(BaseModel):
    items: list[MerchantProfileAdmin]
    total: int
    page: int
    page_size: int
