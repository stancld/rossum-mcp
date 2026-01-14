from __future__ import annotations

from anthropic.types import ImageBlockParam, TextBlockParam

UserContent = str | list[TextBlockParam | ImageBlockParam]
