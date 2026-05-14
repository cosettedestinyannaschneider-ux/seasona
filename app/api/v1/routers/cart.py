from typing import Any

from fastapi import APIRouter, Depends, status

from app.core.dependencies import require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.schemas.cart import CartItemCreate, CartItemUpdate, CartPublic


router = APIRouter()


@router.get("", response_model=CartPublic)
def get_cart(
    current_buyer: Any = Depends(require_roles(UserRole.BUYER)),
    db: Any = Depends(get_db),
) -> CartPublic:
    from app.services.commerce.service import get_cart

    return get_cart(db, current_buyer)


@router.post("/items", response_model=CartPublic, status_code=status.HTTP_201_CREATED)
def add_cart_item(
    payload: CartItemCreate,
    current_buyer: Any = Depends(require_roles(UserRole.BUYER)),
    db: Any = Depends(get_db),
) -> CartPublic:
    from app.services.commerce.service import add_cart_item

    try:
        cart = add_cart_item(
            db,
            current_buyer,
            sku_id=payload.sku_id,
            quantity=payload.quantity,
            selected=payload.selected,
        )
        db.commit()
        return cart
    except Exception:
        db.rollback()
        raise


@router.patch("/items/{item_id}", response_model=CartPublic)
def update_cart_item(
    item_id: int,
    payload: CartItemUpdate,
    current_buyer: Any = Depends(require_roles(UserRole.BUYER)),
    db: Any = Depends(get_db),
) -> CartPublic:
    from app.services.commerce.service import update_cart_item

    try:
        cart = update_cart_item(
            db,
            current_buyer,
            item_id,
            quantity=payload.quantity,
            selected=payload.selected,
        )
        db.commit()
        return cart
    except Exception:
        db.rollback()
        raise


@router.delete("/items/{item_id}", response_model=CartPublic)
def remove_cart_item(
    item_id: int,
    current_buyer: Any = Depends(require_roles(UserRole.BUYER)),
    db: Any = Depends(get_db),
) -> CartPublic:
    from app.services.commerce.service import remove_cart_item

    try:
        cart = remove_cart_item(db, current_buyer, item_id)
        db.commit()
        return cart
    except Exception:
        db.rollback()
        raise
