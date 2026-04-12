from __future__ import annotations


def truncate_output(output: str, limit: int) -> str:
    if len(output) <= limit:
        return output
    truncation_point = output.rfind("\n", 0, limit)
    if truncation_point <= 0:
        truncation_point = limit
    return output[:truncation_point] + "\n... (truncated)"
