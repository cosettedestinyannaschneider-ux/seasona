from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select, update

from app.core.dependencies import require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import Address
from app.schemas.user import AddressCreate, AddressListResponse, AddressPublic


router = APIRouter()

_MAX_ADDRESS_COUNT = 20


def _address_query(user_id: int):
    return (
        select(Address)
        .where(Address.user_id == user_id)
        .order_by(Address.is_default.desc(), Address.updated_at.desc(), Address.id.desc())
    )


@router.get("", response_model=AddressListResponse)
def list_addresses(
    current_buyer: Any = Depends(require_roles(UserRole.BUYER)),
    db: Any = Depends(get_db),
) -> AddressListResponse:
    items = db.execute(_address_query(current_buyer.id)).scalars().all()
    return AddressListResponse(items=items, total=len(items))


@router.post("", response_model=AddressPublic, status_code=status.HTTP_201_CREATED)
def create_address(
    payload: AddressCreate,
    current_buyer: Any = Depends(require_roles(UserRole.BUYER)),
    db: Any = Depends(get_db),
) -> AddressPublic:
    try:
        address_count = db.execute(
            select(func.count(Address.id)).where(Address.user_id == current_buyer.id)
        ).scalar_one()
        if address_count >= _MAX_ADDRESS_COUNT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Address book limit reached.",
            )

        is_default = payload.is_default or address_count == 0
        if is_default:
            db.execute(
                update(Address)
                .where(Address.user_id == current_buyer.id)
                .values(is_default=False)
            )

        address = Address(
            user_id=current_buyer.id,
            receiver_name=payload.receiver_name,
            receiver_phone=payload.receiver_phone,
            province=payload.province,
            city=payload.city,
            district=payload.district,
            detail=payload.detail,
            is_default=is_default,
        )
        db.add(address)
        db.commit()
        db.refresh(address)
        return AddressPublic.model_validate(address)
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


@router.delete("/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_address(
    address_id: int,
    current_buyer: Any = Depends(require_roles(UserRole.BUYER)),
    db: Any = Depends(get_db),
) -> Response:
    try:
        address = db.execute(
            select(Address)
            .where(Address.id == address_id)
            .where(Address.user_id == current_buyer.id)
            .limit(1)
        ).scalar_one_or_none()
        if address is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found.")

        was_default = address.is_default
        db.delete(address)
        db.flush()
        if was_default:
            next_address = db.execute(_address_query(current_buyer.id).limit(1)).scalar_one_or_none()
            if next_address is not None:
                next_address.is_default = True
        db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
