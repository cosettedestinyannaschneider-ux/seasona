from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import DisputeStatus, OrderStatus, PaymentStatus, RefundStatus, UserRole
from app.models.mixins import TimestampMixin
from app.models.sqltypes import enum_column


class Cart(TimestampMixin, Base):
    __tablename__ = "cart"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("user_account.id"), unique=True)


class CartItem(TimestampMixin, Base):
    __tablename__ = "cart_item"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    cart_id: Mapped[int] = mapped_column(ForeignKey("cart.id"), index=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey("product_sku.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    selected: Mapped[bool] = mapped_column(default=True)


class CheckoutPayment(TimestampMixin, Base):
    __tablename__ = "checkout_payment"
    __table_args__ = (
        UniqueConstraint("buyer_id", "idempotency_key", name="uq_checkout_payment_buyer_idempotency_key"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    payment_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("user_account.id"), index=True)
    status: Mapped[PaymentStatus] = mapped_column(enum_column(PaymentStatus), index=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    freight_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    payable_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    receiver_snapshot_json: Mapped[dict] = mapped_column(JSON)
    payment_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC) + timedelta(minutes=20),
        nullable=False,
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(128), index=True)


class Order(TimestampMixin, Base):
    __tablename__ = "purchase_order"
    __table_args__ = (
        UniqueConstraint("buyer_id", "idempotency_key", name="uq_order_buyer_idempotency_key"),
        UniqueConstraint(
            "buyer_id",
            "seller_id",
            "checkout_idempotency_key",
            name="uq_order_buyer_seller_checkout_key",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    order_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    payment_id: Mapped[int | None] = mapped_column(ForeignKey("checkout_payment.id"), index=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("user_account.id"), index=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("merchant_profile.id"), index=True)
    status: Mapped[OrderStatus] = mapped_column(enum_column(OrderStatus), index=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    freight_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    payable_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    receiver_snapshot_json: Mapped[dict] = mapped_column(JSON)
    expected_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payment_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC) + timedelta(minutes=20),
        nullable=False,
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_shipped: Mapped[bool] = mapped_column(Boolean, default=False)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str | None] = mapped_column(String(128), index=True)
    checkout_idempotency_key: Mapped[str | None] = mapped_column(String(128), index=True)


class OrderItem(TimestampMixin, Base):
    __tablename__ = "order_item"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("purchase_order.id"), index=True)
    spu_id: Mapped[int] = mapped_column(ForeignKey("product_spu.id"), index=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey("product_sku.id"), index=True)
    product_name_snapshot: Mapped[str] = mapped_column(String(128))
    spec_name_snapshot: Mapped[str] = mapped_column(String(128))
    cover_image_url_snapshot: Mapped[str | None] = mapped_column(String(512))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    quantity: Mapped[int] = mapped_column(Integer)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))


class RefundApplication(TimestampMixin, Base):
    __tablename__ = "refund_application"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("purchase_order.id"), index=True)
    order_item_id: Mapped[int | None] = mapped_column(ForeignKey("order_item.id"), index=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("user_account.id"), index=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("merchant_profile.id"), index=True)
    status: Mapped[RefundStatus] = mapped_column(enum_column(RefundStatus), index=True)
    reason: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    evidence_images_json: Mapped[list[str] | None] = mapped_column(JSON)
    admin_note: Mapped[str | None] = mapped_column(Text)
    seller_deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    seller_handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    seller_note: Mapped[str | None] = mapped_column(Text)
    seller_handler_id: Mapped[int | None] = mapped_column(ForeignKey("user_account.id"))


class RefundDispute(TimestampMixin, Base):
    __tablename__ = "refund_dispute"
    __table_args__ = (UniqueConstraint("refund_id", name="uq_refund_dispute_refund_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    refund_id: Mapped[int] = mapped_column(ForeignKey("refund_application.id"), index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("purchase_order.id"), index=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("user_account.id"), index=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("merchant_profile.id"), index=True)
    initiator_id: Mapped[int] = mapped_column(ForeignKey("user_account.id"), index=True)
    initiator_role: Mapped[UserRole] = mapped_column(enum_column(UserRole), index=True)
    status: Mapped[DisputeStatus] = mapped_column(
        enum_column(DisputeStatus),
        default=DisputeStatus.PENDING,
        index=True,
    )
    reason: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    evidence_images_json: Mapped[list[str] | None] = mapped_column(JSON)
    resolution_note: Mapped[str | None] = mapped_column(Text)
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("user_account.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OrderStatusLog(TimestampMixin, Base):
    __tablename__ = "order_status_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("purchase_order.id"), index=True)
    from_status: Mapped[OrderStatus | None] = mapped_column(enum_column(OrderStatus))
    to_status: Mapped[OrderStatus] = mapped_column(enum_column(OrderStatus), index=True)
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("user_account.id"))
    note: Mapped[str | None] = mapped_column(Text)
