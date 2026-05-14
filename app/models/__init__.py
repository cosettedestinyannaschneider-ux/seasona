"""SQLAlchemy model registry.

Importing this package registers all concrete models on ``Base.metadata``.
"""

from app.models.ai import AiChatMessage, AiChatSession
from app.models.order import (
    Cart,
    CartItem,
    Order,
    OrderItem,
    OrderStatusLog,
    RefundApplication,
    RefundDispute,
)
from app.models.product import (
    ProductCategory,
    ProductImage,
    ProductReview,
    ProductSku,
    ProductSpu,
    ProductTraceability,
)
from app.models.user import Address, MerchantProfile, UserAccount
from app.models.wallet import WalletAccount, WalletLedger

__all__ = [
    "AiChatMessage",
    "AiChatSession",
    "Address",
    "Cart",
    "CartItem",
    "MerchantProfile",
    "Order",
    "OrderItem",
    "OrderStatusLog",
    "ProductCategory",
    "ProductImage",
    "ProductReview",
    "ProductSku",
    "ProductSpu",
    "ProductTraceability",
    "RefundApplication",
    "RefundDispute",
    "UserAccount",
    "WalletAccount",
    "WalletLedger",
]
