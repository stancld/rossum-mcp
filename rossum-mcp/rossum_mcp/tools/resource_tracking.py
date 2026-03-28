from __future__ import annotations

import logging
from dataclasses import asdict, is_dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

logger = logging.getLogger(__name__)

TRACKED_RESOURCES_KEY = "_tracked_resources"


def track_resource(tracked: list[dict[str, Any]], entity_type: str, entity_id: int | str, data: Any) -> None:
    """Append a side-effect resource to the tracked list.

    Converts dataclass/dict data to a plain dict for serialization.
    Non-convertible data is silently skipped.
    """
    if isinstance(data, dict):
        payload = data
    elif is_dataclass(data) and not isinstance(data, type):
        payload = asdict(data)
    else:
        logger.warning(f"track_resource: cannot convert {type(data).__name__} to dict, skipping")
        return

    tracked.append({"entity_type": entity_type, "entity_id": str(entity_id), "data": payload})


def embed_tracked_resources(result: Any, tracked: list[dict[str, Any]]) -> Any:
    """Embed tracked resources into the tool result if any were collected.

    If tracked is non-empty, converts the result to a dict (via dataclass asdict
    if needed) and adds the _tracked_resources key. Returns result unchanged if
    tracked is empty or result is not convertible.
    """
    if not tracked:
        return result

    if isinstance(result, dict):
        result_dict = dict(result)
    elif is_dataclass(result) and not isinstance(result, type):
        result_dict = asdict(result)
    else:
        logger.warning(f"embed_tracked_resources: cannot convert {type(result).__name__} to dict")
        return result

    result_dict[TRACKED_RESOURCES_KEY] = tracked
    return result_dict
