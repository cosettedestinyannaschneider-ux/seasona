from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError

from app.core.dependencies import get_optional_current_user, require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.schemas.product import CategoryNode, ProductDetail, ProductListResponse, ProductMerchantPublic, ProductSort
from app.schemas.review import ReviewCreate, ReviewEligibilityResponse, ReviewListResponse, ReviewPublic, ReviewDraftUpsert


router = APIRouter()


def _review_conflict_message(order_id: int | None, order_item_id: int | None) -> str:
    return "Order already reviewed." if order_id is not None or order_item_id is not None else "Product already reviewed."


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
    sort_by: str = Query(default="likes", pattern="^(likes|newest)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: Any | None = Depends(get_optional_current_user),
    db: Any = Depends(get_db),
) -> ReviewListResponse:
    from app.services.catalog.service import get_public_product_detail
    from app.services.commerce.service import list_reviews

    get_public_product_detail(db, spu_id)
    return list_reviews(
        db,
        spu_id=spu_id,
        public_only=True,
        sort_by=sort_by,
        viewer=current_user,
        page=page,
        page_size=page_size,
    )


@router.get("/{spu_id}/review-eligibility", response_model=ReviewEligibilityResponse)
def get_review_eligibility(
    spu_id: int,
    current_buyer: Any = Depends(require_roles(UserRole.BUYER)),
    db: Any = Depends(get_db),
) -> ReviewEligibilityResponse:
    from app.services.commerce.service import get_product_review_eligibility

    return get_product_review_eligibility(db, current_buyer, spu_id)


@router.post("/{spu_id}/reviews", response_model=ReviewPublic, status_code=status.HTTP_201_CREATED)
def create_product_review(
    spu_id: int,
    payload: ReviewCreate,
    background_tasks: BackgroundTasks,
    current_buyer: Any = Depends(require_roles(UserRole.BUYER)),
    db: Any = Depends(get_db),
) -> ReviewPublic:
    from app.services.commerce.service import create_product_review as create_review

    try:
        review = create_review(
            db,
            current_buyer,
            spu_id=spu_id,
            order_id=payload.order_id,
            order_item_id=payload.order_item_id,
            rating=payload.rating,
            content=payload.content,
            images_json=payload.images_json,
        )
        db.commit()
        from app.services.search.service import refresh_product_search_document_for_review_if_due

        background_tasks.add_task(refresh_product_search_document_for_review_if_due, review.spu_id)
        return review
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_review_conflict_message(payload.order_id, payload.order_item_id),
        ) from exc
    except Exception:
        db.rollback()
        raise


@router.get("/{spu_id}/review-draft", response_model=ReviewPublic | None)
def get_product_review_draft(
    spu_id: int,
    order_id: int | None = None,
    order_item_id: int | None = None,
    current_buyer: Any = Depends(require_roles(UserRole.BUYER)),
    db: Any = Depends(get_db),
) -> ReviewPublic | None:
    from app.services.commerce.service import get_product_review_draft as get_draft

    return get_draft(db, current_buyer, spu_id=spu_id, order_id=order_id, order_item_id=order_item_id)


@router.put("/{spu_id}/review-draft", response_model=ReviewPublic)
def save_product_review_draft(
    spu_id: int,
    payload: ReviewDraftUpsert,
    current_buyer: Any = Depends(require_roles(UserRole.BUYER)),
    db: Any = Depends(get_db),
) -> ReviewPublic:
    from app.services.commerce.service import save_product_review_draft as save_draft

    try:
        review = save_draft(
            db,
            current_buyer,
            spu_id=spu_id,
            order_id=payload.order_id,
            order_item_id=payload.order_item_id,
            rating=payload.rating,
            content=payload.content,
            images_json=payload.images_json,
        )
        db.commit()
        return review
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_review_conflict_message(payload.order_id, payload.order_item_id),
        ) from exc
    except Exception:
        db.rollback()
        raise
