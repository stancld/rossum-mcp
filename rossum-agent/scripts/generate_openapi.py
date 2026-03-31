"""Generate OpenAPI spec JSON from the FastAPI app."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from rossum_agent.api.main import app


def main() -> None:
    default_path = Path(__file__).resolve().parent.parent / "rossum_agent" / "api" / "openapi.json"
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(app.openapi(), indent=2) + "\n")
    print(f"OpenAPI spec written to {output_path}")


if __name__ == "__main__":
    main()
