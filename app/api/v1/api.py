from fastapi import APIRouter

from app.api.v1.routers import (
    addresses,
    admin,
    ai,
    auth,
    cart,
    health,
    orders,
    products,
    reviews,
    refunds,
    search,
    seller,
    uploads,
)


api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(reviews.router, prefix="/reviews", tags=["reviews"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(addresses.router, prefix="/addresses", tags=["addresses"])
api_router.include_router(cart.router, prefix="/cart", tags=["cart"])
api_router.include_router(orders.router, prefix="/orders", tags=["orders"])
api_router.include_router(refunds.router, prefix="/refunds", tags=["refunds"])
api_router.include_router(seller.router, prefix="/seller", tags=["seller"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(uploads.router, prefix="/uploads", tags=["uploads"])
