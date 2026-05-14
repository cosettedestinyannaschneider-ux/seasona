from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.core.dependencies import require_roles
from app.models.enums import MerchantAuditStatus, UserRole
from app.schemas.upload import ImageUploadResponse


router = APIRouter()

_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

try:
    import multipart  # type: ignore  # noqa: F401

    _MULTIPART_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on local environment
    _MULTIPART_AVAILABLE = False


def _extension_from_content_type(content_type: str) -> str:
    if content_type == "image/jpeg":
        return ".jpg"
    if content_type == "image/png":
        return ".png"
    if content_type == "image/webp":
        return ".webp"
    if content_type == "image/gif":
        return ".gif"
    return ""


if _MULTIPART_AVAILABLE:
    from fastapi import File, UploadFile

    async def _store_image(
        *,
        file: UploadFile,
        settings: Settings,
        subdir: str,
    ) -> ImageUploadResponse:
        content_type = file.content_type or "application/octet-stream"
        if content_type not in _ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only jpeg, png, webp and gif images are allowed.",
            )

        data = await file.read()
        max_bytes = settings.max_upload_size_mb * 1024 * 1024
        if len(data) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Image exceeds {settings.max_upload_size_mb} MB.",
            )

        suffix = _extension_from_content_type(content_type)
        filename = f"{uuid4().hex}{suffix}"
        target_dir = settings.media_root / subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / filename
        target_path.write_bytes(data)

        media_prefix = settings.media_url_prefix.rstrip("/")
        return ImageUploadResponse(
            image_url=f"{media_prefix}/{subdir}/{filename}",
            filename=filename,
            content_type=content_type,
            size=len(data),
        )

    @router.post("/images", response_model=ImageUploadResponse, status_code=status.HTTP_201_CREATED)
    async def upload_product_image(
        file: UploadFile = File(...),
        current_seller: Any = Depends(require_roles(UserRole.SELLER)),
        settings: Settings = Depends(get_settings),
    ) -> ImageUploadResponse:
        _ensure_product_image_upload_allowed(current_seller)
        return await _store_image(file=file, settings=settings, subdir="products")

    @router.post("/avatars", response_model=ImageUploadResponse, status_code=status.HTTP_201_CREATED)
    async def upload_avatar_image(
        file: UploadFile = File(...),
        current_user: Any = Depends(require_roles(UserRole.BUYER, UserRole.ADMIN)),
        settings: Settings = Depends(get_settings),
    ) -> ImageUploadResponse:
        _ = current_user
        return await _store_image(file=file, settings=settings, subdir="avatars")

    @router.post(
        "/merchant-audit-images",
        response_model=ImageUploadResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def upload_merchant_audit_image(
        file: UploadFile = File(...),
        current_seller: Any = Depends(require_roles(UserRole.SELLER)),
        settings: Settings = Depends(get_settings),
    ) -> ImageUploadResponse:
        _ensure_merchant_audit_upload_allowed(current_seller)
        return await _store_image(file=file, settings=settings, subdir="merchant-audit")
else:

    @router.post("/images", status_code=status.HTTP_501_NOT_IMPLEMENTED)
    def upload_product_image(
        current_seller: Any = Depends(require_roles(UserRole.SELLER)),
    ) -> dict[str, str]:
        _ensure_product_image_upload_allowed(current_seller)
        return {"detail": "Image upload requires python-multipart to be installed."}

    @router.post("/avatars", status_code=status.HTTP_501_NOT_IMPLEMENTED)
    def upload_avatar_image(
        current_user: Any = Depends(require_roles(UserRole.BUYER, UserRole.ADMIN)),
    ) -> dict[str, str]:
        _ = current_user
        return {"detail": "Image upload requires python-multipart to be installed."}

    @router.post("/merchant-audit-images", status_code=status.HTTP_501_NOT_IMPLEMENTED)
    def upload_merchant_audit_image(
        current_seller: Any = Depends(require_roles(UserRole.SELLER)),
    ) -> dict[str, str]:
        _ensure_merchant_audit_upload_allowed(current_seller)
        return {"detail": "Image upload requires python-multipart to be installed."}


def _seller_merchant(current_seller: Any) -> Any:
    merchant = getattr(current_seller, "merchant_profile", None)
    if merchant is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seller profile is missing.",
        )
    return merchant


def _ensure_product_image_upload_allowed(current_seller: Any) -> None:
    merchant = _seller_merchant(current_seller)
    merchant_status = getattr(merchant.audit_status, "value", merchant.audit_status)
    if merchant_status != MerchantAuditStatus.APPROVED.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Product images can only be uploaded by approved merchants.",
        )


def _ensure_merchant_audit_upload_allowed(current_seller: Any) -> None:
    merchant = _seller_merchant(current_seller)
    merchant_status = getattr(merchant.audit_status, "value", merchant.audit_status)
    if merchant_status not in {
        MerchantAuditStatus.DRAFT.value,
        MerchantAuditStatus.REJECTED.value,
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audit images can only be uploaded before submission or after rejection.",
        )
