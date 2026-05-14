from typing import Any

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import get_current_user, require_roles
from app.db.session import get_db
from app.models.enums import DisputeStatus, RefundStatus, UserRole
from app.schemas.dispute import DisputeCreate, DisputeListResponse, DisputePublic
from app.schemas.refund import RefundCreate, RefundListResponse, RefundPublic


router = APIRouter()


@router.get("/disputes", response_model=DisputeListResponse)
def list_my_disputes(
    status_filter: DisputeStatus | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: Any = Depends(get_current_user),
    db: Any = Depends(get_db),
) -> DisputeListResponse:
    from app.services.commerce.service import list_refund_disputes

    try:
        response = list_refund_disputes(
            db,
            current_user,
            status_filter=status_filter,
            page=page,
            page_size=page_size,
        )
        db.commit()
        return response
    except Exception:
        db.rollback()
        raise


@router.post("/disputes", response_model=DisputePublic, status_code=status.HTTP_201_CREATED)
def create_dispute(
    payload: DisputeCreate,
    current_user: Any = Depends(get_current_user),
    db: Any = Depends(get_db),
) -> DisputePublic:
    from app.services.commerce.service import create_refund_dispute

    try:
        dispute = create_refund_dispute(
            db,
            current_user,
            refund_id=payload.refund_id,
            reason=payload.reason,
            description=payload.description,
            evidence_images_json=payload.evidence_images_json,
        )
        db.commit()
        return dispute
    except Exception:
        db.rollback()
        raise


@router.get("", response_model=RefundListResponse)
def list_my_refunds(
    status_filter: RefundStatus | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: Any = Depends(get_current_user),
    db: Any = Depends(get_db),
) -> RefundListResponse:
    from app.services.commerce.service import list_refunds

    try:
        response = list_refunds(
            db,
            current_user,
            status_filter=status_filter,
            page=page,
            page_size=page_size,
        )
        db.commit()
        return response
    except Exception:
        db.rollback()
        raise


@router.post("", response_model=RefundPublic, status_code=status.HTTP_201_CREATED)
def create_refund(
    payload: RefundCreate,
    current_buyer: Any = Depends(require_roles(UserRole.BUYER)),
    db: Any = Depends(get_db),
) -> RefundPublic:
    from app.services.commerce.service import create_refund_application

    try:
        refund = create_refund_application(
            db,
            current_buyer,
            order_id=payload.order_id,
            reason=payload.reason,
            description=payload.description,
            amount=payload.amount,
            evidence_images_json=payload.evidence_images_json,
        )
        db.commit()
        return RefundPublic.model_validate(refund, from_attributes=True)
    except Exception:
        db.rollback()
        raise
