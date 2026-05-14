from __future__ import annotations

from enum import StrEnum
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import UserRole
from app.schemas.user import UserPublic


USERNAME_PATTERN = r"^[A-Za-z][A-Za-z0-9]{3,63}$"
_USERNAME_RE = re.compile(USERNAME_PATTERN)


class RegisterMethod(StrEnum):
    PHONE = "phone"
    EMAIL = "email"


def _strip_required(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required.")
    return text


def _strip_optional(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_email(value: str | None) -> str | None:
    if value and "@" not in value:
        raise ValueError("email must contain @.")
    return value.lower() if value else None


def _validate_phone(value: str | None) -> str | None:
    if value and not value.isdigit():
        raise ValueError("phone must contain only digits.")
    return value


def _validate_username(value: Any, field_name: str = "username") -> str:
    text = _strip_required(value, field_name)
    if not _USERNAME_RE.fullmatch(text):
        raise ValueError(
            "username must start with a letter and contain only letters and numbers."
        )
    return text


class BuyerRegisterRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "username": "buyerDemo1",
                    "password": "password123",
                    "register_method": "phone",
                    "phone": "13800000000",
                },
                {
                    "username": "buyerMail1",
                    "password": "password123",
                    "register_method": "email",
                    "email": "buyer@example.com",
                },
            ]
        }
    )

    username: str = Field(
        min_length=4,
        max_length=64,
        pattern=USERNAME_PATTERN,
        description="Buyer username. Must start with a letter and contain only letters and numbers.",
    )
    password: str = Field(min_length=8, max_length=128, description="Login password.")
    register_method: RegisterMethod = Field(
        default=RegisterMethod.PHONE,
        description="Buyer registration method. Phone registration requires phone; email registration requires email.",
    )
    phone: str | None = Field(default=None, max_length=32, description="Phone number, unique within buyer role.")
    email: str | None = Field(default=None, max_length=128, description="Email, unique within buyer role.")
    nickname: str | None = Field(default=None, max_length=64, description="Optional nickname.")

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: Any) -> str:
        return _validate_username(value)

    @field_validator("phone", "email", "nickname", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Any) -> str | None:
        return _strip_optional(value)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        return _normalize_email(value)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        return _validate_phone(value)

    @model_validator(mode="after")
    def validate_contact_method(self) -> "BuyerRegisterRequest":
        if self.register_method == RegisterMethod.PHONE:
            if not self.phone:
                raise ValueError("phone is required when register_method is phone.")
            if self.email:
                raise ValueError("email must be empty when register_method is phone.")
        if self.register_method == RegisterMethod.EMAIL:
            if not self.email:
                raise ValueError("email is required when register_method is email.")
            if self.phone:
                raise ValueError("phone must be empty when register_method is email.")
        return self


class SellerRegisterRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "shop_name": "Demo Farm",
                    "username": "sellerDemo1",
                    "contact_name": "Zhang San",
                    "phone": "13900000000",
                    "password": "password123",
                    "email": "seller@example.com",
                    "shop_description": "Course project demo merchant.",
                }
            ]
        }
    )

    shop_name: str = Field(min_length=1, max_length=128, description="Shop name. Duplicates are allowed.")
    username: str = Field(
        min_length=4,
        max_length=64,
        pattern=USERNAME_PATTERN,
        description="Seller username. Must start with a letter and contain only letters and numbers.",
    )
    contact_name: str = Field(min_length=1, max_length=64, description="Merchant contact person.")
    phone: str = Field(min_length=1, max_length=32, description="Contact phone, unique within seller role.")
    password: str = Field(min_length=8, max_length=128, description="Login password.")
    email: str | None = Field(default=None, max_length=128, description="Optional email, unique within seller role if present.")
    shop_description: str | None = Field(default=None, description="Optional public shop description.")

    @field_validator("shop_name", "contact_name", "phone", mode="before")
    @classmethod
    def normalize_required_text(cls, value: Any) -> str:
        return _strip_required(value, "field")

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: Any) -> str:
        return _validate_username(value)

    @field_validator("email", "shop_description", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Any) -> str | None:
        return _strip_optional(value)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        return _normalize_email(value)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        return _validate_phone(value) or value


class RoleLoginRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "identifier": "buyerDemo1",
                    "password": "password123",
                },
                {
                    "identifier": "13800000000",
                    "password": "password123",
                },
            ]
        }
    )

    identifier: str = Field(min_length=1, max_length=128, description="Username, phone, or email within the selected role.")
    password: str = Field(min_length=8, max_length=128, description="Login password.")

    @field_validator("identifier", mode="before")
    @classmethod
    def normalize_identifier(cls, value: Any) -> str:
        return _strip_required(value, "identifier")


class AdminLoginRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "username": "admin",
                    "password": "password123",
                }
            ]
        }
    )

    username: str = Field(min_length=1, max_length=64, description="Admin username.")
    password: str = Field(min_length=8, max_length=128, description="Admin password.")

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: Any) -> str:
        return _strip_required(value, "username")


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AuthResponse(AuthTokenResponse):
    user: UserPublic


class PasswordResetRequest(BaseModel):
    role: UserRole = Field(description="Only buyer and seller password reset is exposed.")
    method: RegisterMethod
    identifier: str = Field(min_length=1, max_length=128)

    @field_validator("identifier", mode="before")
    @classmethod
    def normalize_identifier(cls, value: Any) -> str:
        return _strip_required(value, "identifier")

    @model_validator(mode="after")
    def validate_role_and_identifier(self) -> "PasswordResetRequest":
        if self.role not in {UserRole.BUYER, UserRole.SELLER}:
            raise ValueError("password reset only supports buyer and seller accounts.")
        if self.method == RegisterMethod.PHONE:
            self.identifier = _validate_phone(self.identifier) or self.identifier
        if self.method == RegisterMethod.EMAIL:
            normalized = _normalize_email(self.identifier)
            if normalized is None:
                raise ValueError("email is required.")
            self.identifier = normalized
        return self


class PasswordResetTicket(BaseModel):
    reset_token: str
    token_type: str = "password_reset"
    expires_in: int
    masked_target: str


class PasswordResetConfirmRequest(BaseModel):
    reset_token: str = Field(min_length=20)
    new_password: str = Field(min_length=8, max_length=128)


class PasswordResetConfirmResponse(BaseModel):
    detail: str = "password reset"
