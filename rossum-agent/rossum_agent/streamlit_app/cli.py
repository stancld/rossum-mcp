"""CLI entry point for Rossum Agent Streamlit application."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def main() -> None:
    """Launch the Rossum Agent Streamlit application."""
    app_path = Path(__file__).parent / "app.py"
    streamlit_executable = shutil.which("streamlit")
    if not streamlit_executable:
        print("Error: 'streamlit' executable not found in PATH", file=sys.stderr)
        sys.exit(1)
    sys.exit(subprocess.call([streamlit_executable, "run", str(app_path), *sys.argv[1:]]))


if __name__ == "__main__":
    main()
