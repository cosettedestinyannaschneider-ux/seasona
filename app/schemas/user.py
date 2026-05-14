from __future__ import annotations

from datetime import datetime

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import MerchantAuditStatus, UserRole, UserStatus


class MerchantProfilePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    shop_name: str
    shop_logo_url: str | None = None
    shop_description: str | None = None
    audit_status: MerchantAuditStatus
    audit_reason: str | None = None


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: UserRole
    status: UserStatus
    nickname: str | None = None
    avatar_url: str | None = None
    phone: str | None = None
    email: str | None = None
    merchant_profile: MerchantProfilePublic | None = None


class UserProfileUpdate(BaseModel):
    nickname: str | None = Field(default=None, max_length=64)
    avatar_url: str | None = Field(default=None, max_length=512)

    @field_validator("nickname", "avatar_url", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class UserContactUpdate(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=128)

    @field_validator("phone", "email", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value and not value.isdigit():
            raise ValueError("phone must contain only digits.")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if value and "@" not in value:
            raise ValueError("email must contain @.")
        return value.lower() if value else None

    @model_validator(mode="after")
    def require_contact_field(self) -> "UserContactUpdate":
        changed_fields = self.model_fields_set - {"current_password"}
        if not changed_fields:
            raise ValueError("phone or email is required.")
        return self


class UserPasswordUpdate(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class AddressBase(BaseModel):
    receiver_name: str = Field(min_length=1, max_length=64)
    receiver_phone: str = Field(min_length=1, max_length=32)
    province: str = Field(min_length=1, max_length=64)
    city: str = Field(min_length=1, max_length=64)
    district: str = Field(min_length=1, max_length=64)
    detail: str = Field(min_length=1, max_length=255)

    @field_validator(
        "receiver_name",
        "receiver_phone",
        "province",
        "city",
        "district",
        "detail",
        mode="before",
    )
    @classmethod
    def normalize_required_text(cls, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("field is required.")
        return text

    @field_validator("receiver_phone")
    @classmethod
    def validate_receiver_phone(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("phone must contain only digits.")
        return value


class AddressCreate(AddressBase):
    is_default: bool = False


class AddressPublic(AddressBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    is_default: bool
    created_at: datetime
    updated_at: datetime


class AddressListResponse(BaseModel):
    items: list[AddressPublic]
    total: int


class AdminUserPublic(UserPublic):
    model_config = ConfigDict(from_attributes=True)

    created_at: datetime
    updated_at: datetime


class AdminUserListResponse(BaseModel):
    items: list[AdminUserPublic]
    total: int
    page: int
    page_size: int
