from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.enums import ProductStatus
from app.models.product import ProductSku, ProductSpu
from app.schemas.product import ProductCreate, ProductImageCreate, ProductSkuSave, ProductUpdate
from app.services.catalog import service as catalog_service
from test.factories import create_admin, create_category, create_product, create_seller


pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def no_search_sync(monkeypatch) -> None:
    monkeypatch.setattr("app.services.search.service.upsert_product_search_document", lambda *args, **kwargs: True)
    monkeypatch.setattr("app.services.search.service.remove_product_search_document", lambda *args, **kwargs: True)


def test_product_review_lifecycle_and_stock_only_update(db_session) -> None:
    seller = create_seller(db_session)
    admin = create_admin(db_session)
    category = create_category(db_session)
    product = catalog_service.create_product(
        db_session,
        seller,
        ProductCreate(
            category_id=category.id,
            name="Tomato",
            description="Fresh",
            skus=[{"spec_name": "500g", "unit": "pack", "price": Decimal("8.80"), "stock_available": 10}],
            images=[ProductImageCreate(image_url="/media/tomato.png")],
        ),
    )
    db_session.flush()

    assert product.status == ProductStatus.DRAFT

    catalog_service.submit_product_for_review(db_session, seller, product.id)
    assert product.status == ProductStatus.PENDING_REVIEW
    catalog_service.review_product(db_session, admin, product.id, approved=True, reason="ok")
    assert product.status == ProductStatus.ONLINE

    sku = db_session.execute(select(ProductSku).where(ProductSku.spu_id == product.id)).scalar_one()
    catalog_service.update_product(
        db_session,
        seller,
        product.id,
        ProductUpdate(
            skus=[
                ProductSkuSave(
                    id=sku.id,
                    version=sku.version,
                    spec_name=sku.spec_name,
                    unit=sku.unit,
                    price=sku.price,
                    original_price=sku.original_price,
                    stock_available=12,
                )
            ]
        ),
    )
    assert product.status == ProductStatus.ONLINE

    catalog_service.update_product(db_session, seller, product.id, ProductUpdate(name="Tomato Plus"))
    assert product.status == ProductStatus.PENDING_REVIEW


def test_sku_version_conflict_and_locked_stock_deletion_are_rejected(db_session) -> None:
    seller = create_seller(db_session)
    product, sku = create_product(db_session, seller, status=ProductStatus.ONLINE)

    with pytest.raises(HTTPException) as conflict:
        catalog_service.update_product(
            db_session,
            seller,
            product.id,
            ProductUpdate(
                skus=[
                    ProductSkuSave(
                        id=sku.id,
                        version=sku.version + 1,
                        spec_name=sku.spec_name,
                        unit=sku.unit,
                        price=sku.price,
                        stock_available=sku.stock_available + 1,
                    )
                ]
            ),
        )
    assert conflict.value.status_code == 409

    keeper = ProductSku(
        spu_id=product.id,
        spec_name="1kg",
        spec_attrs_json=None,
        unit="pack",
        price=Decimal("12.80"),
        original_price=None,
        stock_available=5,
        stock_locked=0,
        version=0,
    )
    db_session.add(keeper)
    db_session.flush()
    sku.stock_locked = 1
    db_session.flush()
    with pytest.raises(HTTPException) as locked:
        catalog_service.update_product(
            db_session,
            seller,
            product.id,
            ProductUpdate(
                skus=[
                    ProductSkuSave(
                        id=keeper.id,
                        version=keeper.version,
                        spec_name=keeper.spec_name,
                        unit=keeper.unit,
                        price=keeper.price,
                        original_price=keeper.original_price,
                        stock_available=keeper.stock_available,
                    )
                ]
            ),
        )
    assert locked.value.status_code == 400


def test_soft_deleted_product_is_hidden_from_public_detail(db_session) -> None:
    seller = create_seller(db_session)
    product, _ = create_product(db_session, seller, status=ProductStatus.OFFLINE)

    catalog_service.delete_seller_product(db_session, seller, product.id)

    assert db_session.get(ProductSpu, product.id).deleted_at is not None
    with pytest.raises(HTTPException) as missing:
        catalog_service.get_public_product_detail(db_session, product.id)
    assert missing.value.status_code == 404
