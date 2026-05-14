from enum import StrEnum


class UserRole(StrEnum):
    BUYER = "buyer"
    SELLER = "seller"
    ADMIN = "admin"


class UserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class WalletStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class MerchantAuditStatus(StrEnum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


class ProductStatus(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    ONLINE = "online"
    OFFLINE = "offline"
    REJECTED = "rejected"


class OrderStatus(StrEnum):
    WAIT_PAY = "WAIT_PAY"
    EXPIRED = "EXPIRED"
    PAID = "PAID"
    SHIPPED = "SHIPPED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    REFUND_PENDING = "REFUND_PENDING"
    REFUNDED = "REFUNDED"
    DISPUTED = "DISPUTED"


class RefundStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    DISPUTED = "disputed"


class DisputeStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReviewStatus(StrEnum):
    VISIBLE = "visible"
    HIDDEN = "hidden"
    PENDING = "pending"


class LedgerDirection(StrEnum):
    IN = "in"
    OUT = "out"
    FREEZE = "freeze"
    UNFREEZE = "unfreeze"


class WalletBizType(StrEnum):
    RECHARGE = "recharge"
    ORDER_PAY = "order_pay"
    REFUND = "refund"
    SELLER_SETTLEMENT = "seller_settlement"
    ADMIN_ADJUST = "admin_adjust"


class AiMessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
