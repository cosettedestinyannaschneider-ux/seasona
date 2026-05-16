from datetime import date
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Index,
    ForeignKey,
    and_,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import ProductStatus, ReviewStatus
from app.models.mixins import TimestampMixin
from app.models.sqltypes import enum_column


class ProductCategory(TimestampMixin, Base):
    __tablename__ = "product_category"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("product_category.id"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(64), index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ProductSpu(TimestampMixin, Base):
    __tablename__ = "product_spu"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchant_profile.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("product_category.id"), index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    origin_place: Mapped[str | None] = mapped_column(String(128), index=True)
    cover_image_url: Mapped[str | None] = mapped_column(String(512))
    review_reason: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("user_account.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[ProductStatus] = mapped_column(
        enum_column(ProductStatus),
        default=ProductStatus.DRAFT,
        index=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class ProductSku(TimestampMixin, Base):
    __tablename__ = "product_sku"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_product_sku_price_nonnegative"),
        CheckConstraint(
            "stock_available >= 0",
            name="ck_product_sku_stock_available_nonnegative",
        ),
        CheckConstraint(
            "stock_locked >= 0",
            name="ck_product_sku_stock_locked_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    spu_id: Mapped[int] = mapped_column(ForeignKey("product_spu.id"), index=True)
    spec_name: Mapped[str] = mapped_column(String(128))
    spec_attrs_json: Mapped[dict | None] = mapped_column(JSON)
    unit: Mapped[str] = mapped_column(String(32))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    original_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    stock_available: Mapped[int] = mapped_column(Integer, default=0)
    stock_locked: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=0)


class ProductImage(TimestampMixin, Base):
    __tablename__ = "product_image"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    spu_id: Mapped[int] = mapped_column(ForeignKey("product_spu.id"), index=True)
    sku_id: Mapped[int | None] = mapped_column(ForeignKey("product_sku.id"), index=True)
    image_url: Mapped[str] = mapped_column(String(512))
    is_cover: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class ProductTraceability(TimestampMixin, Base):
    __tablename__ = "product_traceability"
    __table_args__ = (UniqueConstraint("spu_id", name="uq_traceability_spu_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    spu_id: Mapped[int] = mapped_column(ForeignKey("product_spu.id"), index=True)
    trace_code: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    farm_name: Mapped[str | None] = mapped_column(String(128))
    harvest_date: Mapped[date | None] = mapped_column(Date)
    inspection_result: Mapped[str | None] = mapped_column(String(128))
    cold_chain_info: Mapped[str | None] = mapped_column(String(255))
    trace_steps_json: Mapped[list[dict] | None] = mapped_column(JSON)


class ProductReview(TimestampMixin, Base):
    __tablename__ = "product_review"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_account.id"), index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_order.id"), index=True)
    order_item_id: Mapped[int | None] = mapped_column(ForeignKey("order_item.id"), index=True)
    spu_id: Mapped[int] = mapped_column(ForeignKey("product_spu.id"), index=True)
    sku_id: Mapped[int | None] = mapped_column(ForeignKey("product_sku.id"), index=True)
    rating: Mapped[int | None] = mapped_column(Integer)
    content: Mapped[str | None] = mapped_column(Text)
    images_json: Mapped[list[str] | None] = mapped_column(JSON)
    status: Mapped[ReviewStatus] = mapped_column(
        enum_column(ReviewStatus),
        default=ReviewStatus.VISIBLE,
        index=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    __table_args__ = (
        Index(
            "uq_product_review_order_spu_active",
            "order_id",
            "spu_id",
            unique=True,
            postgresql_where=and_(order_id.is_not(None), deleted_at.is_(None)),
        ),
        Index(
            "uq_product_review_user_spu_free_active",
            "user_id",
            "spu_id",
            unique=True,
            postgresql_where=and_(order_id.is_(None), deleted_at.is_(None)),
        ),
    )


class ProductReviewComment(TimestampMixin, Base):
    __tablename__ = "product_review_comment"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("product_review.id"), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("product_review_comment.id"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("user_account.id"), index=True)
    author_role: Mapped[str] = mapped_column(String(16), index=True)
    content: Mapped[str] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class ProductReviewLike(TimestampMixin, Base):
    __tablename__ = "product_review_like"
    __table_args__ = (UniqueConstraint("review_id", "user_id", name="uq_product_review_like_review_user"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("product_review.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_account.id"), index=True)
