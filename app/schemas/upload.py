from __future__ import annotations

from pydantic import BaseModel


class ImageUploadResponse(BaseModel):
    image_url: str
    filename: str
    content_type: str
    size: int
