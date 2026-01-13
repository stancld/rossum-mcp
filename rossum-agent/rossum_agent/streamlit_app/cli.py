"""CLI entry point for Rossum Agent Streamlit application."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    """Launch the Rossum Agent Streamlit application."""
    app_path = Path(__file__).parent / "app.py"
    sys.exit(subprocess.call([sys.executable, "-m", "streamlit", "run", str(app_path), *sys.argv[1:]]))


if __name__ == "__main__":
    main()
