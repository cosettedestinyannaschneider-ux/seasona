from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, status

from app.core.dependencies import get_optional_current_user, require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.schemas.review import ReviewCommentCreate, ReviewDetailPublic, ReviewPublic


router = APIRouter()


@router.get("/{review_id}", response_model=ReviewDetailPublic)
def get_review_detail(
    review_id: int,
    current_user: Any | None = Depends(get_optional_current_user),
    db: Any = Depends(get_db),
) -> ReviewDetailPublic:
    from app.services.commerce.service import get_review_detail as load_review_detail

    return load_review_detail(db, review_id, viewer=current_user)


@router.post("/{review_id}/like", response_model=ReviewPublic)
def like_review(
    review_id: int,
    current_buyer: Any = Depends(require_roles(UserRole.BUYER)),
    db: Any = Depends(get_db),
) -> ReviewPublic:
    from app.services.commerce.service import like_product_review

    try:
        review = like_product_review(db, current_buyer, review_id=review_id, liked=True)
        db.commit()
        return review
    except Exception:
        db.rollback()
        raise


@router.delete("/{review_id}/like", response_model=ReviewPublic)
def unlike_review(
    review_id: int,
    current_buyer: Any = Depends(require_roles(UserRole.BUYER)),
    db: Any = Depends(get_db),
) -> ReviewPublic:
    from app.services.commerce.service import like_product_review

    try:
        review = like_product_review(db, current_buyer, review_id=review_id, liked=False)
        db.commit()
        return review
    except Exception:
        db.rollback()
        raise


@router.post("/{review_id}/comments", response_model=ReviewDetailPublic, status_code=status.HTTP_201_CREATED)
def create_comment(
    review_id: int,
    payload: ReviewCommentCreate,
    current_buyer: Any = Depends(require_roles(UserRole.BUYER)),
    db: Any = Depends(get_db),
) -> ReviewDetailPublic:
    from app.services.commerce.service import create_review_comment

    try:
        detail = create_review_comment(
            db,
            current_buyer,
            review_id=review_id,
            parent_id=payload.parent_id,
            content=payload.content,
        )
        db.commit()
        return detail
    except Exception:
        db.rollback()
        raise


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_review(
    review_id: int,
    background_tasks: BackgroundTasks,
    current_buyer: Any = Depends(require_roles(UserRole.BUYER)),
    db: Any = Depends(get_db),
) -> None:
    from app.services.commerce.service import delete_product_review

    try:
        spu_id = delete_product_review(db, current_buyer, review_id=review_id)
        db.commit()
        from app.services.search.service import refresh_product_search_document_for_review_if_due

        background_tasks.add_task(refresh_product_search_document_for_review_if_due, spu_id)
    except Exception:
        db.rollback()
        raise


@router.delete("/comments/{comment_id}", response_model=ReviewDetailPublic)
def delete_comment(
    comment_id: int,
    current_user: Any = Depends(require_roles(UserRole.BUYER, UserRole.SELLER)),
    db: Any = Depends(get_db),
) -> ReviewDetailPublic:
    from app.services.commerce.service import delete_review_comment

    try:
        detail = delete_review_comment(db, current_user, comment_id=comment_id)
        db.commit()
        return detail
    except Exception:
        db.rollback()
        raise
