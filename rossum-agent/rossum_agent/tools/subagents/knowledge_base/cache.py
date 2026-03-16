"""In-memory cache for pre-scraped Knowledge Base articles."""

from __future__ import annotations

import importlib.resources
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from importlib.resources.abc import Traversable
    from typing import Any

_KB_DATA_PATH_ENV = "ROSSUM_KB_DATA_PATH"


def _bundled_kb_path() -> Traversable:
    return importlib.resources.files("rossum_agent.data").joinpath("rossum-kb.json")


class KBCache:
    def __init__(self, cache_path: Path | None = None) -> None:
        self._cache_path = cache_path
        self._data: dict[str, Any] | None = None
        self._mtime: float = 0

    def load(self) -> dict[str, Any]:
        path = self._resolve_path()

        # Traversable (e.g. inside zips) doesn't support stat — skip mtime caching
        current_mtime = path.stat().st_mtime if isinstance(path, Path) else 0.0

        if self._data is not None and current_mtime == self._mtime:
            return self._data

        data = json.loads(path.read_text())
        self._data = data
        self._mtime = current_mtime
        return data

    def _resolve_path(self) -> Path | Traversable:
        local_path = os.environ.get(_KB_DATA_PATH_ENV)
        if local_path:
            p = Path(local_path)
            if p.exists():
                return p
            raise FileNotFoundError(f"{_KB_DATA_PATH_ENV} points to non-existent file: {local_path}")
        if self._cache_path is not None:
            return self._cache_path
        return _bundled_kb_path()


cache = KBCache()
