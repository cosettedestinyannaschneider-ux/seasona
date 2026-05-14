from typing import Any

from fastapi import APIRouter, Depends, Query

from app.db.session import get_db
from app.schemas.search import ProductSearchResponse, ProductSearchSort


router = APIRouter()


@router.get("", response_model=ProductSearchResponse)
def search_products(
    q: str = "",
    category_id: int | None = None,
    origin_place: str | None = None,
    sort_by: ProductSearchSort = ProductSearchSort.RELEVANCE,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Any = Depends(get_db),
) -> ProductSearchResponse:
    from app.services.search.service import search_products as search_products_service

    return search_products_service(
        db,
        query=q,
        category_id=category_id,
        origin_place=origin_place,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
    )
