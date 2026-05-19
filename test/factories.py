from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from itertools import count
from typing import Any
from uuid import uuid4

from polyfactory.factories.pydantic_factory import ModelFactory

from app.core.config import Settings
from app.core.security import hash_password
from app.models.enums import MerchantAuditStatus, OrderStatus, ProductStatus, UserRole, UserStatus, WalletStatus
from app.models.order import Cart, Order, OrderItem
from app.models.product import ProductCategory, ProductSku, ProductSpu
from app.schemas.auth import BuyerRegisterRequest, RegisterMethod, SellerRegisterRequest
from app.schemas.wallet import WalletRechargeRequest
from app.models.user import MerchantProfile, UserAccount
from app.models.wallet import WalletAccount


_counter = count(1)


class BuyerRegisterRequestFactory(ModelFactory[BuyerRegisterRequest]):
    __model__ = BuyerRegisterRequest

    username = "BuyerFactory1"
    password = "password123"
    register_method = RegisterMethod.PHONE
    phone = "13800009999"
    email = None
    nickname = "Buyer Factory"


class SellerRegisterRequestFactory(ModelFactory[SellerRegisterRequest]):
    __model__ = SellerRegisterRequest

    shop_name = "Factory Farm"
    username = "SellerFactory1"
    contact_name = "Owner"
    phone = "13900009999"
    password = "password123"
    email = "seller.factory@example.com"
    shop_description = "factory seller"


class WalletRechargeRequestFactory(ModelFactory[WalletRechargeRequest]):
    __model__ = WalletRechargeRequest

    amount = Decimal("100.00")
    idempotency_key = "recharge-factory-001"


def unique(prefix: str = "t") -> str:
    return f"{prefix}{next(_counter)}{uuid4().hex[:6]}"


def password_hash(password: str = "password123", settings: Settings | None = None) -> str:
    if settings is None:
        return hash_password(password, time_cost=1, memory_cost=8192, parallelism=1)
    return hash_password(
        password,
        time_cost=settings.argon2_time_cost,
        memory_cost=settings.argon2_memory_cost,
        parallelism=settings.argon2_parallelism,
        hash_len=settings.argon2_hash_len,
        salt_len=settings.argon2_salt_len,
    )


def create_user(
    db: Any,
    *,
    role: UserRole = UserRole.BUYER,
    username: str | None = None,
    password: str = "password123",
    status: UserStatus = UserStatus.ACTIVE,
    settings: Settings | None = None,
    phone: str | None = None,
    email: str | None = None,
) -> UserAccount:
    suffix = next(_counter)
    user = UserAccount(
        username=username or f"{role.value}{suffix}",
        password_hash=password_hash(password, settings),
        role=role,
        status=status,
        nickname=f"{role.value} user",
        avatar_url=None,
        phone=phone,
        email=email,
    )
    db.add(user)
    db.flush()
    db.add(
        WalletAccount(
            user_id=user.id,
            available_balance=Decimal("0.00"),
            frozen_balance=Decimal("0.00"),
            version=0,
            status=WalletStatus.ACTIVE,
        )
    )
    if role == UserRole.BUYER:
        db.add(Cart(buyer_id=user.id))
    db.flush()
    return user


def create_buyer(db: Any, **kwargs: Any) -> UserAccount:
    return create_user(db, role=UserRole.BUYER, **kwargs)


def create_admin(db: Any, **kwargs: Any) -> UserAccount:
    return create_user(db, role=UserRole.ADMIN, **kwargs)


def create_seller(
    db: Any,
    *,
    audit_status: MerchantAuditStatus = MerchantAuditStatus.APPROVED,
    settings: Settings | None = None,
    **kwargs: Any,
) -> UserAccount:
    seller = create_user(db, role=UserRole.SELLER, settings=settings, **kwargs)
    merchant = MerchantProfile(
        user_id=seller.id,
        shop_name=unique("shop"),
        shop_logo_url=None,
        shop_description="test merchant",
        contact_name="Seller",
        contact_phone=seller.phone or "13900000000",
        audit_material_text=None,
        audit_images_json=[],
        audit_status=audit_status,
        audit_reason=None,
    )
    db.add(merchant)
    db.flush()
    seller.merchant_profile = merchant
    return seller


def create_category(db: Any, *, name: str | None = None, is_active: bool = True) -> ProductCategory:
    category = ProductCategory(parent_id=None, name=name or unique("cat"), sort_order=0, is_active=is_active)
    db.add(category)
    db.flush()
    return category


def create_product(
    db: Any,
    seller: UserAccount,
    *,
    category: ProductCategory | None = None,
    status: ProductStatus = ProductStatus.ONLINE,
    stock: int = 20,
    price: str = "8.80",
    name: str | None = None,
) -> tuple[ProductSpu, ProductSku]:
    if category is None:
        category = create_category(db)
    merchant = seller.merchant_profile
    product = ProductSpu(
        merchant_id=merchant.id,
        category_id=category.id,
        name=name or unique("product"),
        description="test product",
        origin_place="test origin",
        cover_image_url="/media/products/test.png",
        review_reason=None,
        reviewed_by=None,
        reviewed_at=None,
        status=status,
        deleted_at=None,
    )
    db.add(product)
    db.flush()
    sku = ProductSku(
        spu_id=product.id,
        spec_name="500g",
        spec_attrs_json=None,
        unit="pack",
        price=Decimal(price),
        original_price=Decimal("9.90"),
        stock_available=stock,
        stock_locked=0,
        version=0,
    )
    db.add(sku)
    db.flush()
    return product, sku


def receiver_snapshot() -> dict[str, str]:
    return {
        "receiver_name": "Test Buyer",
        "receiver_phone": "13800000000",
        "province": "Zhejiang",
        "city": "Hangzhou",
        "district": "Xihu",
        "detail": "Test road 1",
    }


def create_paid_order(
    db: Any,
    buyer: UserAccount,
    seller: UserAccount,
    *,
    shipped: bool = False,
    completed: bool = False,
    amount: Decimal = Decimal("8.80"),
) -> Order:
    product, sku = create_product(db, seller, price=str(amount), stock=20)
    sku.stock_available -= 1
    sku.stock_locked += 1
    status = OrderStatus.COMPLETED if completed else (OrderStatus.SHIPPED if shipped else OrderStatus.PAID)
    now = datetime.now(UTC)
    order = Order(
        order_no=unique("SO"),
        payment_id=None,
        buyer_id=buyer.id,
        seller_id=seller.merchant_profile.id,
        status=status,
        total_amount=amount,
        freight_amount=Decimal("0.00"),
        payable_amount=amount,
        receiver_snapshot_json=receiver_snapshot(),
        expected_delivery_at=now + timedelta(days=3),
        payment_expires_at=now + timedelta(minutes=20),
        paid_at=now,
        is_shipped=shipped or completed,
        shipped_at=now if shipped or completed else None,
        idempotency_key=unique("order"),
        checkout_idempotency_key=unique("checkout"),
    )
    db.add(order)
    db.flush()
    db.add(
        OrderItem(
            order_id=order.id,
            spu_id=product.id,
            sku_id=sku.id,
            product_name_snapshot=product.name,
            spec_name_snapshot=sku.spec_name,
            cover_image_url_snapshot=product.cover_image_url,
            unit_price=amount,
            quantity=1,
            total_amount=amount,
        )
    )
    db.flush()
    return order
