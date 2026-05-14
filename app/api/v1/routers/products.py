from typing import Any

from fastapi import APIRouter, Depends, Query

from app.db.session import get_db
from app.schemas.product import CategoryNode, ProductDetail, ProductListResponse, ProductMerchantPublic, ProductSort
from app.schemas.review import ReviewListResponse


router = APIRouter()


@router.get("/categories", response_model=list[CategoryNode])
def list_categories(db: Any = Depends(get_db)) -> list[CategoryNode]:
    from app.services.catalog.service import list_category_tree

    return list_category_tree(db, active_only=True)


@router.get("", response_model=ProductListResponse)
def list_products(
    q: str = "",
    category_id: int | None = None,
    origin_place: str | None = None,
    merchant_id: int | None = None,
    sort_by: ProductSort = ProductSort.NEWEST,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Any = Depends(get_db),
) -> ProductListResponse:
    from app.services.catalog.service import list_public_products

    return list_public_products(
        db,
        keyword=q,
        category_id=category_id,
        origin_place=origin_place,
        merchant_id=merchant_id,
        sort_by=sort_by.value,
        page=page,
        page_size=page_size,
    )


@router.get("/merchants/{merchant_id}", response_model=ProductMerchantPublic)
def get_merchant(merchant_id: int, db: Any = Depends(get_db)) -> ProductMerchantPublic:
    from app.services.catalog.service import get_public_merchant_detail

    return get_public_merchant_detail(db, merchant_id)


@router.get("/{spu_id}", response_model=ProductDetail)
def get_product(spu_id: int, db: Any = Depends(get_db)) -> ProductDetail:
    from app.services.catalog.service import get_public_product_detail

    return get_public_product_detail(db, spu_id)


@router.get("/{spu_id}/reviews", response_model=ReviewListResponse)
def list_product_reviews(
    spu_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Any = Depends(get_db),
) -> ReviewListResponse:
    from app.services.catalog.service import get_public_product_detail
    from app.services.commerce.service import list_reviews

    get_public_product_detail(db, spu_id)
    return list_reviews(db, spu_id=spu_id, public_only=True, page=page, page_size=page_size)
