from sqlalchemy import BigInteger, Boolean, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import MerchantAuditStatus, UserRole, UserStatus
from app.models.mixins import TimestampMixin
from app.models.sqltypes import enum_column


class UserAccount(TimestampMixin, Base):
    __tablename__ = "user_account"
    __table_args__ = (
        UniqueConstraint("role", "username", name="uq_user_role_username"),
        UniqueConstraint("role", "phone", name="uq_user_role_phone"),
        UniqueConstraint("role", "email", name="uq_user_role_email"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(enum_column(UserRole), index=True)
    status: Mapped[UserStatus] = mapped_column(
        enum_column(UserStatus),
        default=UserStatus.ACTIVE,
        index=True,
    )
    nickname: Mapped[str | None] = mapped_column(String(64))
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    phone: Mapped[str | None] = mapped_column(String(32), index=True)
    email: Mapped[str | None] = mapped_column(String(128), index=True)

    merchant_profile: Mapped["MerchantProfile | None"] = relationship(
        back_populates="user",
        uselist=False,
    )


class MerchantProfile(TimestampMixin, Base):
    __tablename__ = "merchant_profile"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id"),
        unique=True,
        index=True,
    )
    shop_name: Mapped[str] = mapped_column(String(128), index=True)
    shop_logo_url: Mapped[str | None] = mapped_column(String(512))
    shop_description: Mapped[str | None] = mapped_column(Text)
    contact_name: Mapped[str] = mapped_column(String(64))
    contact_phone: Mapped[str] = mapped_column(String(32))
    audit_material_text: Mapped[str | None] = mapped_column(Text)
    audit_images_json: Mapped[list[str] | None] = mapped_column(JSON)
    audit_status: Mapped[MerchantAuditStatus] = mapped_column(
        enum_column(MerchantAuditStatus),
        default=MerchantAuditStatus.DRAFT,
        index=True,
    )
    audit_reason: Mapped[str | None] = mapped_column(Text)

    user: Mapped[UserAccount] = relationship(back_populates="merchant_profile")


class Address(TimestampMixin, Base):
    __tablename__ = "address"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_account.id"), index=True)
    receiver_name: Mapped[str] = mapped_column(String(64))
    receiver_phone: Mapped[str] = mapped_column(String(32))
    province: Mapped[str] = mapped_column(String(64))
    city: Mapped[str] = mapped_column(String(64))
    district: Mapped[str] = mapped_column(String(64))
    detail: Mapped[str] = mapped_column(String(255))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
