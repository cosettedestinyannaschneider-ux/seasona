from __future__ import annotations

import pytest

from app.api.v1.routers.uploads import _is_valid_image_signature, _normalize_content_type


pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("content_type", "data"),
    [
        ("image/jpeg", b"\xff\xd8\xff\xe0jpeg-data"),
        ("image/png", b"\x89PNG\r\n\x1a\npng-data"),
        ("image/gif", b"GIF87agif-data"),
        ("image/gif", b"GIF89agif-data"),
        ("image/webp", b"RIFF\x18\x00\x00\x00WEBPwebp-data"),
    ],
)
def test_image_signature_accepts_supported_image_headers(content_type: str, data: bytes) -> None:
    assert _is_valid_image_signature(content_type, data)


@pytest.mark.parametrize("content_type", ["image/jpeg", "image/png", "image/gif", "image/webp"])
def test_image_signature_rejects_declared_images_with_wrong_content(content_type: str) -> None:
    assert not _is_valid_image_signature(content_type, b"<script>alert(1)</script>")


def test_upload_content_type_is_normalized_before_validation() -> None:
    assert _normalize_content_type("IMAGE/PNG; charset=binary") == "image/png"
    assert _normalize_content_type(None) == "application/octet-stream"
