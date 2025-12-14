from __future__ import annotations

from typing import Literal, TypedDict


class Base64ImageSource(TypedDict):
    """Source for a base64-encoded image."""

    type: Literal["base64"]
    media_type: str
    data: str


class ImageContentBlock(TypedDict):
    """A content block representing an image."""

    type: Literal["image"]
    source: Base64ImageSource


class TextContentBlock(TypedDict):
    """A content block representing text."""

    type: Literal["text"]
    text: str


ContentBlock = ImageContentBlock | TextContentBlock

UserContent = str | list[ContentBlock]
