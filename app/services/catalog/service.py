from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, UTC
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select

from app.models.enums import MerchantAuditStatus, ProductStatus, ReviewStatus, UserRole, UserStatus
from app.models.order import OrderItem
from app.models.product import ProductCategory, ProductImage, ProductReview, ProductSku, ProductSpu, ProductTraceability
from app.models.user import MerchantProfile, UserAccount
from app.schemas.product import (
    CategoryNode,
    ProductCreate,
    ProductDetail,
    ProductImageCreate,
    ProductImagePublic,
    ProductListResponse,
    ProductMerchantPublic,
    ProductSkuPublic,
    ProductTraceabilityPublic,
    ProductUpdate,
    ProductSkuCreate,
    ProductSkuSave,
)


def _get_role_value(user: Any) -> str:
    return getattr(user.role, "value", user.role)


def _require_seller_merchant(user: Any) -> MerchantProfile:
    merchant = getattr(user, "merchant_profile", None)
    if merchant is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seller profile is missing.",
        )
    merchant_status = getattr(merchant.audit_status, "value", merchant.audit_status)
    if merchant_status != MerchantAuditStatus.APPROVED.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Merchant account is not approved yet.",
        )
    return merchant


def _ensure_category_exists(db: Any, category_id: int) -> ProductCategory:
    category = db.get(ProductCategory, category_id)
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found.",
        )
    if not category.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category is inactive.",
        )
    return category


def _get_category(db: Any, category_id: int) -> ProductCategory:
    category = db.get(ProductCategory, category_id)
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found.",
        )
    return category


def _ensure_category_parent_is_valid(
    db: Any,
    *,
    category_id: int,
    parent_id: int,
) -> ProductCategory:
    if parent_id == category_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category cannot be its own parent.",
        )

    visited: set[int] = set()
    current_id: int | None = parent_id
    while current_id is not None:
        if current_id in visited:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category hierarchy contains a cycle.",
            )
        visited.add(current_id)
        current = _ensure_category_exists(db, current_id)
        if current.id == category_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category hierarchy contains a cycle.",
            )
        current_id = current.parent_id

    return _ensure_category_exists(db, parent_id)


def _ensure_product_ownership(product: ProductSpu, merchant_id: int) -> None:
    if product.merchant_id != merchant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this product.",
        )


def _ensure_product_not_deleted(product: ProductSpu) -> None:
    if product.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )


def _public_product_filters() -> list[Any]:
    return [
        ProductSpu.deleted_at.is_(None),
        ProductSpu.status == ProductStatus.ONLINE,
        MerchantProfile.audit_status == MerchantAuditStatus.APPROVED,
        UserAccount.status == UserStatus.ACTIVE,
        ProductCategory.is_active.is_(True),
    ]


def _sync_product_discovery_indexes(db: Any, product: ProductSpu) -> None:
    from app.services.search.service import remove_product_search_document, upsert_product_search_document

    if product.deleted_at is None and product.status == ProductStatus.ONLINE:
        upsert_product_search_document(db, product.id)
        return

    remove_product_search_document(product.id)


def build_category_tree(categories: Sequence[ProductCategory]) -> list[CategoryNode]:
    nodes: dict[int, CategoryNode] = {}
    roots: list[CategoryNode] = []

    for category in categories:
        nodes[category.id] = CategoryNode.model_validate(category)

    for category in categories:
        node = nodes[category.id]
        if category.parent_id is not None and category.parent_id in nodes:
            nodes[category.parent_id].children.append(node)
        else:
            roots.append(node)

    return roots


def list_category_tree(db: Any, *, active_only: bool = False) -> list[CategoryNode]:
    statement = select(ProductCategory)
    if active_only:
        statement = statement.where(ProductCategory.is_active.is_(True))
    categories = db.execute(
        statement.order_by(ProductCategory.sort_order.asc(), ProductCategory.id.asc())
    ).scalars().all()
    return build_category_tree(categories)


def create_category(db: Any, payload: Any) -> ProductCategory:
    if payload.parent_id is not None:
        _ensure_category_exists(db, payload.parent_id)
    category = ProductCategory(
        parent_id=payload.parent_id,
        name=payload.name,
        sort_order=payload.sort_order,
        is_active=payload.is_active,
    )
    db.add(category)
    db.flush()
    return category


def update_category(db: Any, category_id: int, payload: Any) -> ProductCategory:
    category = _get_category(db, category_id)
    if "parent_id" in getattr(payload, "model_fields_set", set()):
        if payload.parent_id is None:
            category.parent_id = None
        else:
            _ensure_category_parent_is_valid(
                db,
                category_id=category.id,
                parent_id=payload.parent_id,
            )
            category.parent_id = payload.parent_id
    if payload.name is not None:
        category.name = payload.name
    if payload.sort_order is not None:
        category.sort_order = payload.sort_order
    if payload.is_active is not None:
        category.is_active = payload.is_active
    db.flush()
    from app.services.search.service import sync_category_search_documents

    sync_category_search_documents(db, category.id)
    return category


def delete_category(db: Any, category_id: int) -> None:
    category = _get_category(db, category_id)
    child_count = db.execute(
        select(func.count(ProductCategory.id)).where(ProductCategory.parent_id == category.id)
    ).scalar_one()
    if child_count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category has child categories.",
        )
    product_count = db.execute(
        select(func.count(ProductSpu.id)).where(ProductSpu.category_id == category.id)
    ).scalar_one()
    if product_count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category has products.",
        )
    db.delete(category)
    db.flush()


def _product_sku_stats_subquery():
    return (
        select(
            ProductSku.spu_id.label("spu_id"),
            func.min(ProductSku.price).label("min_price"),
            func.max(ProductSku.price).label("max_price"),
            func.coalesce(func.sum(ProductSku.stock_available), 0).label("stock_total"),
            func.count(ProductSku.id).label("sku_count"),
        )
        .group_by(ProductSku.spu_id)
        .subquery()
    )


def _product_image_stats_subquery():
    return (
        select(
            ProductImage.spu_id.label("spu_id"),
            func.count(ProductImage.id).label("image_count"),
        )
        .group_by(ProductImage.spu_id)
        .subquery()
    )


def _product_review_stats_subquery():
    return (
        select(
            ProductReview.spu_id.label("spu_id"),
            func.avg(ProductReview.rating).label("average_rating"),
            func.count(ProductReview.id).label("review_count"),
        )
        .where(ProductReview.status == ReviewStatus.VISIBLE)
        .where(ProductReview.deleted_at.is_(None))
        .group_by(ProductReview.spu_id)
        .subquery()
    )


def _row_to_public_product(row: Any) -> dict[str, Any]:
    spu: ProductSpu = row.ProductSpu
    average_rating = getattr(row, "average_rating", None)
    return {
        "id": spu.id,
        "merchant_id": spu.merchant_id,
        "merchant_shop_name": row.shop_name,
        "merchant_shop_logo_url": row.shop_logo_url,
        "category_id": spu.category_id,
        "category_name": row.category_name,
        "name": spu.name,
        "description": spu.description,
        "origin_place": spu.origin_place,
        "cover_image_url": spu.cover_image_url,
        "min_price": row.min_price,
        "max_price": row.max_price,
        "stock_total": int(row.stock_total or 0),
        "image_count": int(row.image_count or 0),
        "average_rating": float(average_rating) if average_rating is not None else None,
        "review_count": int(getattr(row, "review_count", 0) or 0),
        "status": spu.status,
        "review_reason": spu.review_reason,
        "reviewed_by": spu.reviewed_by,
        "reviewed_at": spu.reviewed_at,
        "created_at": spu.created_at,
        "updated_at": spu.updated_at,
    }


def list_public_products(
    db: Any,
    *,
    keyword: str = "",
    category_id: int | None = None,
    origin_place: str | None = None,
    merchant_id: int | None = None,
    sort_by: str = "newest",
    page: int = 1,
    page_size: int = 20,
) -> ProductListResponse:
    sku_stats = _product_sku_stats_subquery()
    image_stats = _product_image_stats_subquery()
    review_stats = _product_review_stats_subquery()

    filters = _public_product_filters()
    if keyword:
        like = f"%{keyword.strip()}%"
        filters.append(
            or_(
                ProductSpu.name.ilike(like),
                ProductSpu.description.ilike(like),
                ProductSpu.origin_place.ilike(like),
            )
        )
    if category_id is not None:
        filters.append(ProductSpu.category_id == category_id)
    if origin_place:
        filters.append(ProductSpu.origin_place.ilike(f"%{origin_place.strip()}%"))
    if merchant_id is not None:
        filters.append(ProductSpu.merchant_id == merchant_id)

    base_statement = (
        select(ProductSpu.id)
        .join(MerchantProfile, ProductSpu.merchant_id == MerchantProfile.id)
        .join(UserAccount, MerchantProfile.user_id == UserAccount.id)
        .join(ProductCategory, ProductSpu.category_id == ProductCategory.id)
        .outerjoin(sku_stats, sku_stats.c.spu_id == ProductSpu.id)
        .outerjoin(image_stats, image_stats.c.spu_id == ProductSpu.id)
        .outerjoin(review_stats, review_stats.c.spu_id == ProductSpu.id)
        .where(and_(*filters))
    )
    total = db.execute(select(func.count()).select_from(base_statement.subquery())).scalar_one()

    min_price_col = func.coalesce(sku_stats.c.min_price, Decimal("0.00"))
    max_price_col = func.coalesce(sku_stats.c.max_price, Decimal("0.00"))
    stock_total_col = func.coalesce(sku_stats.c.stock_total, 0)
    image_count_col = func.coalesce(image_stats.c.image_count, 0)
    review_count_col = func.coalesce(review_stats.c.review_count, 0)

    statement = (
        select(
            ProductSpu,
            MerchantProfile.shop_name.label("shop_name"),
            MerchantProfile.shop_logo_url.label("shop_logo_url"),
            ProductCategory.name.label("category_name"),
            min_price_col.label("min_price"),
            max_price_col.label("max_price"),
            stock_total_col.label("stock_total"),
            image_count_col.label("image_count"),
            review_stats.c.average_rating.label("average_rating"),
            review_count_col.label("review_count"),
        )
        .join(MerchantProfile, ProductSpu.merchant_id == MerchantProfile.id)
        .join(UserAccount, MerchantProfile.user_id == UserAccount.id)
        .join(ProductCategory, ProductSpu.category_id == ProductCategory.id)
        .outerjoin(sku_stats, sku_stats.c.spu_id == ProductSpu.id)
        .outerjoin(image_stats, image_stats.c.spu_id == ProductSpu.id)
        .outerjoin(review_stats, review_stats.c.spu_id == ProductSpu.id)
        .where(and_(*filters))
    )

    if sort_by == "price_asc":
        statement = statement.order_by(min_price_col.asc(), ProductSpu.created_at.desc())
    elif sort_by == "price_desc":
        statement = statement.order_by(max_price_col.desc(), ProductSpu.created_at.desc())
    elif sort_by == "stock_desc":
        statement = statement.order_by(stock_total_col.desc(), ProductSpu.created_at.desc())
    else:
        statement = statement.order_by(ProductSpu.created_at.desc())

    items = []
    for row in db.execute(statement.offset((page - 1) * page_size).limit(page_size)).all():
        items.append(_row_to_public_product(row))

    return ProductListResponse(items=items, total=total, page=page, page_size=page_size)


def get_public_merchant_detail(db: Any, merchant_id: int) -> ProductMerchantPublic:
    merchant = db.execute(
        select(MerchantProfile)
        .join(UserAccount, MerchantProfile.user_id == UserAccount.id)
        .where(
            MerchantProfile.id == merchant_id,
            MerchantProfile.audit_status == MerchantAuditStatus.APPROVED,
            UserAccount.status == UserStatus.ACTIVE,
        )
    ).scalar_one_or_none()
    if merchant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Merchant profile not found.",
        )

    product_count = db.execute(
        select(func.count(ProductSpu.id))
        .join(MerchantProfile, ProductSpu.merchant_id == MerchantProfile.id)
        .join(UserAccount, MerchantProfile.user_id == UserAccount.id)
        .join(ProductCategory, ProductSpu.category_id == ProductCategory.id)
        .where(ProductSpu.merchant_id == merchant_id, *_public_product_filters())
    ).scalar_one()

    return ProductMerchantPublic(
        id=merchant.id,
        shop_name=merchant.shop_name,
        shop_logo_url=merchant.shop_logo_url,
        shop_description=merchant.shop_description,
        product_count=product_count,
    )


def get_product_detail(db: Any, spu_id: int) -> ProductDetail:
    sku_stats = _product_sku_stats_subquery()
    image_stats = _product_image_stats_subquery()
    review_stats = _product_review_stats_subquery()
    statement = (
        select(
            ProductSpu,
            MerchantProfile.shop_name.label("shop_name"),
            MerchantProfile.shop_logo_url.label("shop_logo_url"),
            ProductCategory.name.label("category_name"),
            func.coalesce(sku_stats.c.min_price, Decimal("0.00")).label("min_price"),
            func.coalesce(sku_stats.c.max_price, Decimal("0.00")).label("max_price"),
            func.coalesce(sku_stats.c.stock_total, 0).label("stock_total"),
            func.coalesce(image_stats.c.image_count, 0).label("image_count"),
            review_stats.c.average_rating.label("average_rating"),
            func.coalesce(review_stats.c.review_count, 0).label("review_count"),
        )
        .join(MerchantProfile, ProductSpu.merchant_id == MerchantProfile.id)
        .join(ProductCategory, ProductSpu.category_id == ProductCategory.id)
        .outerjoin(sku_stats, sku_stats.c.spu_id == ProductSpu.id)
        .outerjoin(image_stats, image_stats.c.spu_id == ProductSpu.id)
        .outerjoin(review_stats, review_stats.c.spu_id == ProductSpu.id)
        .where(ProductSpu.id == spu_id)
    )
    row = db.execute(statement).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )

    spu: ProductSpu = row.ProductSpu
    _ensure_product_not_deleted(spu)
    skus = db.execute(
        select(ProductSku).where(ProductSku.spu_id == spu.id).order_by(ProductSku.id.asc())
    ).scalars().all()
    images = db.execute(
        select(ProductImage).where(ProductImage.spu_id == spu.id).order_by(
            ProductImage.is_cover.desc(),
            ProductImage.sort_order.asc(),
            ProductImage.id.asc(),
        )
    ).scalars().all()
    traceability = db.execute(
        select(ProductTraceability).where(ProductTraceability.spu_id == spu.id)
    ).scalar_one_or_none()

    detail = _row_to_public_product(row)
    detail["skus"] = [ProductSkuPublic.model_validate(item) for item in skus]
    detail["images"] = [ProductImagePublic.model_validate(item) for item in images]
    detail["traceability"] = (
        ProductTraceabilityPublic.model_validate(traceability) if traceability else None
    )
    return ProductDetail.model_validate(detail)


def get_public_product_detail(db: Any, spu_id: int) -> ProductDetail:
    detail = get_product_detail(db, spu_id)
    public_row = db.execute(
        select(ProductSpu.id)
        .join(MerchantProfile, ProductSpu.merchant_id == MerchantProfile.id)
        .join(UserAccount, MerchantProfile.user_id == UserAccount.id)
        .join(ProductCategory, ProductSpu.category_id == ProductCategory.id)
        .where(ProductSpu.id == spu_id, *_public_product_filters())
    ).first()
    if public_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )
    return detail


def create_product(db: Any, seller_user: Any, payload: ProductCreate) -> ProductSpu:
    merchant = _require_seller_merchant(seller_user)
    _ensure_category_exists(db, payload.category_id)

    product = ProductSpu(
        merchant_id=merchant.id,
        category_id=payload.category_id,
        name=payload.name,
        description=payload.description,
        origin_place=payload.origin_place,
        cover_image_url=payload.cover_image_url,
        review_reason=None,
        reviewed_by=None,
        reviewed_at=None,
        status=ProductStatus.DRAFT,
    )
    db.add(product)
    db.flush()

    sku_items: list[ProductSkuCreate] = payload.skus
    for sku_item in sku_items:
        db.add(
            ProductSku(
                spu_id=product.id,
                spec_name=sku_item.spec_name,
                spec_attrs_json=sku_item.spec_attrs_json,
                unit=sku_item.unit,
                price=sku_item.price,
                original_price=sku_item.original_price,
                stock_available=sku_item.stock_available,
                stock_locked=0,
                version=0,
            )
        )

    image_items: list[ProductImageCreate] = payload.images
    if image_items and not any(item.is_cover for item in image_items):
        image_items[0] = image_items[0].model_copy(update={"is_cover": True})
    if not product.cover_image_url and image_items:
        product.cover_image_url = image_items[0].image_url
    for image_item in image_items:
        db.add(
            ProductImage(
                spu_id=product.id,
                sku_id=image_item.sku_id,
                image_url=image_item.image_url,
                is_cover=image_item.is_cover,
                sort_order=image_item.sort_order,
            )
        )

    if payload.traceability is not None:
        _ensure_trace_code_available(db, payload.traceability.trace_code, product.id)
        db.add(
            ProductTraceability(
                spu_id=product.id,
                trace_code=payload.traceability.trace_code,
                farm_name=payload.traceability.farm_name,
                harvest_date=payload.traceability.harvest_date,
                inspection_result=payload.traceability.inspection_result,
                cold_chain_info=payload.traceability.cold_chain_info,
                trace_steps_json=[
                    step.model_dump() for step in (payload.traceability.trace_steps_json or [])
                ],
            )
        )

    db.flush()
    return product


def _ensure_editable_product(product: ProductSpu) -> None:
    if product.status == ProductStatus.PENDING_REVIEW:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product pending review cannot be edited.",
        )


def update_product(db: Any, seller_user: Any, spu_id: int, payload: ProductUpdate) -> ProductSpu:
    merchant = _require_seller_merchant(seller_user)
    product = db.get(ProductSpu, spu_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
    )
    _ensure_product_ownership(product, merchant.id)
    _ensure_product_not_deleted(product)
    _ensure_editable_product(product)
    original_status = product.status
    review_required = False

    if payload.category_id is not None:
        if payload.category_id != product.category_id:
            _ensure_category_exists(db, payload.category_id)
            product.category_id = payload.category_id
            review_required = True
    if payload.name is not None:
        if payload.name != product.name:
            product.name = payload.name
            review_required = True
    if payload.description is not None:
        if payload.description != product.description:
            product.description = payload.description
            review_required = True
    if payload.origin_place is not None:
        if payload.origin_place != product.origin_place:
            product.origin_place = payload.origin_place
            review_required = True
    if payload.cover_image_url is not None:
        if payload.cover_image_url != product.cover_image_url:
            product.cover_image_url = payload.cover_image_url
            review_required = True

    if "images" in getattr(payload, "model_fields_set", set()):
        image_changed = _replace_product_images(db, product, payload.images or [])
        review_required = review_required or image_changed

    if "skus" in getattr(payload, "model_fields_set", set()):
        _, sku_review_required = _sync_product_skus(db, product, payload.skus or [])
        review_required = review_required or sku_review_required

    if "traceability" in getattr(payload, "model_fields_set", set()):
        trace_changed = _sync_product_traceability(db, product, payload.traceability)
        review_required = review_required or trace_changed

    if original_status == ProductStatus.ONLINE and review_required:
        product.status = ProductStatus.PENDING_REVIEW
        product.review_reason = None
        product.reviewed_by = None
        product.reviewed_at = None

    db.flush()
    _sync_product_discovery_indexes(db, product)
    return product


def delete_seller_product(db: Any, seller_user: Any, spu_id: int) -> None:
    merchant = _require_seller_merchant(seller_user)
    product = db.execute(
        select(ProductSpu)
        .where(ProductSpu.id == spu_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )
    _ensure_product_ownership(product, merchant.id)
    _ensure_product_not_deleted(product)
    if product.status not in {ProductStatus.DRAFT, ProductStatus.OFFLINE, ProductStatus.REJECTED}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product can only be deleted before review, after rejection, or while offline.",
        )

    product.deleted_at = datetime.now(UTC)
    db.flush()

    from app.services.search.service import remove_product_search_document

    remove_product_search_document(spu_id)


def _image_signature(image: ProductImage | ProductImageCreate) -> tuple[str, int | None, bool, int]:
    return (
        image.image_url,
        image.sku_id,
        bool(image.is_cover),
        int(image.sort_order or 0),
    )


def _replace_product_images(db: Any, product: ProductSpu, image_items: list[ProductImageCreate]) -> bool:
    if image_items and not any(item.is_cover for item in image_items):
        image_items[0] = image_items[0].model_copy(update={"is_cover": True})
    existing = db.execute(
        select(ProductImage)
        .where(ProductImage.spu_id == product.id)
        .order_by(ProductImage.sort_order.asc(), ProductImage.id.asc())
    ).scalars().all()
    current_signature = [_image_signature(image) for image in existing]
    next_signature = [_image_signature(image) for image in image_items]

    if image_items:
        cover = next((item for item in image_items if item.is_cover), image_items[0])
        cover_changed = product.cover_image_url != cover.image_url
        product.cover_image_url = cover.image_url
    else:
        cover_changed = product.cover_image_url is not None
        product.cover_image_url = None

    if current_signature == next_signature:
        return cover_changed

    for image in existing:
        db.delete(image)
    db.flush()
    for image_item in image_items:
        db.add(
            ProductImage(
                spu_id=product.id,
                sku_id=image_item.sku_id,
                image_url=image_item.image_url,
                is_cover=image_item.is_cover,
                sort_order=image_item.sort_order,
            )
        )
    return True


def _trace_signature(traceability: ProductTraceability) -> tuple[Any, ...]:
    return (
        traceability.trace_code,
        traceability.farm_name,
        traceability.harvest_date,
        traceability.inspection_result,
        traceability.cold_chain_info,
        traceability.trace_steps_json or [],
    )


def _payload_trace_signature(traceability: Any) -> tuple[Any, ...]:
    return (
        traceability.trace_code,
        traceability.farm_name,
        traceability.harvest_date,
        traceability.inspection_result,
        traceability.cold_chain_info,
        [step.model_dump() for step in (traceability.trace_steps_json or [])],
    )


def _ensure_trace_code_available(db: Any, trace_code: str, spu_id: int) -> None:
    existing_id = db.execute(
        select(ProductTraceability.spu_id).where(
            ProductTraceability.trace_code == trace_code,
            ProductTraceability.spu_id != spu_id,
        )
    ).scalar_one_or_none()
    if existing_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trace code already exists.",
        )


def _sync_product_traceability(db: Any, product: ProductSpu, traceability: Any | None) -> bool:
    existing = db.execute(
        select(ProductTraceability)
        .where(ProductTraceability.spu_id == product.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()

    if traceability is None:
        if existing is None:
            return False
        db.delete(existing)
        return True

    _ensure_trace_code_available(db, traceability.trace_code, product.id)
    next_signature = _payload_trace_signature(traceability)
    if existing is None:
        db.add(
            ProductTraceability(
                spu_id=product.id,
                trace_code=traceability.trace_code,
                farm_name=traceability.farm_name,
                harvest_date=traceability.harvest_date,
                inspection_result=traceability.inspection_result,
                cold_chain_info=traceability.cold_chain_info,
                trace_steps_json=[step.model_dump() for step in (traceability.trace_steps_json or [])],
            )
        )
        return True

    if _trace_signature(existing) == next_signature:
        return False

    existing.trace_code = traceability.trace_code
    existing.farm_name = traceability.farm_name
    existing.harvest_date = traceability.harvest_date
    existing.inspection_result = traceability.inspection_result
    existing.cold_chain_info = traceability.cold_chain_info
    existing.trace_steps_json = [step.model_dump() for step in (traceability.trace_steps_json or [])]
    return True


def _sync_product_skus(db: Any, product: ProductSpu, sku_items: list[ProductSkuSave]) -> tuple[bool, bool]:
    if not sku_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product must keep at least one SKU.",
        )
    existing_skus = db.execute(
        select(ProductSku)
        .where(ProductSku.spu_id == product.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalars().all()
    existing_by_id = {sku.id: sku for sku in existing_skus}
    keep_ids: set[int] = set()
    changed = False
    review_required = False
    for sku_item in sku_items:
        if sku_item.id is None:
            changed = True
            review_required = True
            db.add(
                ProductSku(
                    spu_id=product.id,
                    spec_name=sku_item.spec_name,
                    spec_attrs_json=sku_item.spec_attrs_json,
                    unit=sku_item.unit,
                    price=sku_item.price,
                    original_price=sku_item.original_price,
                    stock_available=sku_item.stock_available,
                    stock_locked=0,
                )
            )
            continue
        sku = existing_by_id.get(sku_item.id)
        if sku is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="SKU not found.",
            )
        keep_ids.add(sku.id)
        review_fields_changed = (
            sku.spec_name != sku_item.spec_name
            or sku.spec_attrs_json != sku_item.spec_attrs_json
            or sku.unit != sku_item.unit
            or sku.price != sku_item.price
            or sku.original_price != sku_item.original_price
        )
        stock_changed = sku.stock_available != sku_item.stock_available
        if not review_fields_changed and not stock_changed:
            continue
        if sku_item.version is not None and sku.version != sku_item.version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="SKU inventory changed, please refresh and retry.",
            )
        changed = True
        review_required = review_required or review_fields_changed
        sku.spec_name = sku_item.spec_name
        sku.spec_attrs_json = sku_item.spec_attrs_json
        sku.unit = sku_item.unit
        sku.price = sku_item.price
        sku.original_price = sku_item.original_price
        sku.stock_available = sku_item.stock_available
        sku.version += 1

    for sku in existing_skus:
        if sku.id in keep_ids:
            continue
        changed = True
        review_required = True
        if sku.stock_locked > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SKU has locked stock.",
            )
        order_count = db.execute(
            select(func.count(OrderItem.id)).where(OrderItem.sku_id == sku.id)
        ).scalar_one()
        if order_count:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SKU has order records.",
            )
        image_items = db.execute(select(ProductImage).where(ProductImage.sku_id == sku.id)).scalars().all()
        for image in image_items:
            db.delete(image)
        db.delete(sku)
    return changed, review_required


def submit_product_for_review(db: Any, seller_user: Any, spu_id: int) -> ProductSpu:
    merchant = _require_seller_merchant(seller_user)
    product = db.get(ProductSpu, spu_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )
    _ensure_product_ownership(product, merchant.id)
    _ensure_product_not_deleted(product)
    if product.status not in {ProductStatus.DRAFT, ProductStatus.REJECTED, ProductStatus.OFFLINE}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product is not in a submittable state.",
        )
    product.status = ProductStatus.PENDING_REVIEW
    product.review_reason = None
    product.reviewed_by = None
    product.reviewed_at = None
    db.flush()
    _sync_product_discovery_indexes(db, product)
    return product


def list_seller_products(
    db: Any,
    seller_user: Any,
    *,
    page: int = 1,
    page_size: int = 20,
    status_filter: ProductStatus | None = None,
) -> ProductListResponse:
    merchant = _require_seller_merchant(seller_user)
    filters = [ProductSpu.merchant_id == merchant.id, ProductSpu.deleted_at.is_(None)]
    if status_filter is not None:
        filters.append(ProductSpu.status == status_filter)
    statement = select(ProductSpu).where(and_(*filters)).order_by(ProductSpu.created_at.desc())
    total = db.execute(select(func.count()).select_from(statement.subquery())).scalar_one()
    items = []
    for spu in db.execute(statement.offset((page - 1) * page_size).limit(page_size)).scalars().all():
        detail = get_product_detail(db, spu.id)
        items.append(detail.model_dump())
    return ProductListResponse(items=items, total=total, page=page, page_size=page_size)


def list_pending_products(
    db: Any,
    *,
    page: int = 1,
    page_size: int = 20,
) -> ProductListResponse:
    return list_admin_products(
        db,
        page=page,
        page_size=page_size,
        status_filter=ProductStatus.PENDING_REVIEW,
    )


def list_admin_products(
    db: Any,
    *,
    page: int = 1,
    page_size: int = 20,
    status_filter: ProductStatus | None = ProductStatus.PENDING_REVIEW,
) -> ProductListResponse:
    statement = select(ProductSpu).where(
        ProductSpu.status == ProductStatus.PENDING_REVIEW,
        ProductSpu.deleted_at.is_(None),
    )
    if status_filter is None:
        statement = select(ProductSpu).where(ProductSpu.deleted_at.is_(None))
    else:
        statement = select(ProductSpu).where(
            ProductSpu.status == status_filter,
            ProductSpu.deleted_at.is_(None),
        )
    total = db.execute(select(func.count()).select_from(statement.subquery())).scalar_one()
    items = []
    for spu in db.execute(
        statement.order_by(ProductSpu.created_at.desc(), ProductSpu.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all():
        items.append(get_product_detail(db, spu.id).model_dump())
    return ProductListResponse(items=items, total=total, page=page, page_size=page_size)


def review_product(
    db: Any,
    admin_user: Any,
    spu_id: int,
    *,
    approved: bool,
    reason: str | None = None,
) -> ProductSpu:
    if _get_role_value(admin_user) != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permission required.",
        )
    product = db.get(ProductSpu, spu_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )
    _ensure_product_not_deleted(product)
    if product.status != ProductStatus.PENDING_REVIEW:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product is not pending review.",
        )
    product.status = ProductStatus.ONLINE if approved else ProductStatus.REJECTED
    product.review_reason = reason
    product.reviewed_by = getattr(admin_user, "id", None)
    product.reviewed_at = datetime.now(UTC)
    db.flush()
    _sync_product_discovery_indexes(db, product)
    return product


def admin_take_down_product(
    db: Any,
    admin_user: Any,
    spu_id: int,
    *,
    reason: str | None = None,
) -> ProductSpu:
    if _get_role_value(admin_user) != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permission required.",
        )
    product = db.get(ProductSpu, spu_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )
    _ensure_product_not_deleted(product)
    if product.status != ProductStatus.ONLINE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only online products can be taken down.",
        )
    product.status = ProductStatus.REJECTED
    product.review_reason = reason or "商品已由管理员下架。"
    product.reviewed_by = getattr(admin_user, "id", None)
    product.reviewed_at = datetime.now(UTC)
    db.flush()
    _sync_product_discovery_indexes(db, product)
    return product


def set_product_offline(db: Any, seller_user: Any, spu_id: int) -> ProductSpu:
    merchant = _require_seller_merchant(seller_user)
    product = db.get(ProductSpu, spu_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )
    _ensure_product_ownership(product, merchant.id)
    _ensure_product_not_deleted(product)
    if product.status != ProductStatus.ONLINE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only online products can be taken offline.",
        )
    product.status = ProductStatus.OFFLINE
    db.flush()
    _sync_product_discovery_indexes(db, product)
    return product


def set_product_online(db: Any, seller_user: Any, spu_id: int) -> ProductSpu:
    merchant = _require_seller_merchant(seller_user)
    product = db.get(ProductSpu, spu_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )
    _ensure_product_ownership(product, merchant.id)
    _ensure_product_not_deleted(product)
    if product.status == ProductStatus.ONLINE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product is already online.",
        )
    if product.status == ProductStatus.PENDING_REVIEW:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product is already pending review.",
        )
    if product.status not in {ProductStatus.DRAFT, ProductStatus.REJECTED, ProductStatus.OFFLINE}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product is not in a submittable state.",
        )
    product.status = ProductStatus.PENDING_REVIEW
    product.review_reason = None
    product.reviewed_by = None
    product.reviewed_at = None
    db.flush()
    _sync_product_discovery_indexes(db, product)
    return product
