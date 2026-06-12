from __future__ import annotations

import pytest

from app.api.v1.routers.uploads import (
    _content_type_from_signature,
    _normalize_content_type,
    _resolve_image_content_type,
)


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
def test_image_signature_detects_supported_image_headers(content_type: str, data: bytes) -> None:
    assert _content_type_from_signature(data) == content_type


def test_image_content_type_uses_signature_before_declared_type() -> None:
    data = b"\xff\xd8\xff\xe0jpeg-data"

    assert _resolve_image_content_type("application/octet-stream", data) == "image/jpeg"
    assert _resolve_image_content_type("image/png", data) == "image/jpeg"


def test_upload_content_type_is_normalized_before_validation() -> None:
    assert _normalize_content_type("image/jpg") == "image/jpeg"
    assert _normalize_content_type("image/pjpeg") == "image/jpeg"
    assert _normalize_content_type("IMAGE/PNG; charset=binary") == "image/png"
    assert _normalize_content_type(None) == "application/octet-stream"


def test_image_content_type_rejects_unsupported_payload_without_image_hint() -> None:
    assert _resolve_image_content_type("application/octet-stream", b"<script>alert(1)</script>") == ""
