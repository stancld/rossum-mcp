import datetime as dt
import os
import shutil
import tempfile
import uuid
from contextvars import ContextVar
from pathlib import Path

# Context variable for session-specific output directory
# This allows thread-safe per-session output directories
_session_output_dir: ContextVar[Path | None] = ContextVar("session_output_dir", default=None)

# Base directory for all session outputs
BASE_OUTPUT_DIR = Path(tempfile.gettempdir()) / "rossum_agent_outputs"


def create_session_output_dir() -> Path:
    """Create a new session-specific output directory.

    Returns:
        Path to the newly created session directory
    """
    session_id = str(uuid.uuid4())
    session_dir = BASE_OUTPUT_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def set_session_output_dir(output_dir: Path) -> None:
    """Set the output directory for the current session context.

    Args:
        output_dir: Path to the session-specific output directory
    """
    _session_output_dir.set(output_dir)


def get_session_output_dir() -> Path:
    """Get the output directory for the current session.

    Returns:
        Path to session output directory, or creates a default one if not set
    """
    output_dir = _session_output_dir.get()
    if output_dir is None:
        # Fallback for non-session contexts (e.g., CLI usage)
        output_dir = Path("./outputs")
        output_dir.mkdir(exist_ok=True)
    return output_dir


def get_generated_files(output_dir: Path | None = None) -> list[str]:
    """Get list of files in the outputs directory.

    Args:
        output_dir: Optional explicit output directory. If not provided,
                   uses the session context output directory.
    """
    if output_dir is None:
        output_dir = get_session_output_dir()

    if not output_dir.exists():
        return []

    return [str(f.resolve()) for f in output_dir.iterdir() if f.is_file()]


def get_generated_files_with_metadata(output_dir: Path | None = None) -> dict[str, float]:
    """Get files in the outputs directory with their modification times.

    Args:
        output_dir: Optional explicit output directory. If not provided,
                   uses the session context output directory.
    """
    if output_dir is None:
        output_dir = get_session_output_dir()

    if not output_dir.exists():
        return {}

    return {str(f.resolve()): f.stat().st_mtime for f in output_dir.iterdir() if f.is_file()}


def clear_generated_files(output_dir: Path | None = None) -> None:
    """Delete all files in the outputs directory.

    Args:
        output_dir: Optional explicit output directory. If not provided,
                   uses the session context output directory.
    """
    if output_dir is None:
        output_dir = get_session_output_dir()

    if not output_dir.exists():
        return

    for file_path in output_dir.iterdir():
        if file_path.is_file():
            file_path.unlink()


def cleanup_session_output_dir(output_dir: Path) -> None:
    """Remove the entire session output directory.

    Args:
        output_dir: Path to the session output directory to remove
    """
    if output_dir.exists() and output_dir.is_dir():
        shutil.rmtree(output_dir, ignore_errors=True)


def check_env_vars() -> list[tuple[str, str]]:
    """Check if required environment variables are set for Rossum API.

    LLM_MODEL_ID is optional and defaults to a Bedrock model.
    """
    required_vars = {
        "ROSSUM_API_TOKEN": "Rossum API authentication token",
        "ROSSUM_API_BASE_URL": "Rossum API base URL",
    }

    missing = []
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing.append((var, description))

    return missing


def generate_chat_id() -> str:
    unique_id = uuid.uuid4().hex[:12]
    timestamp = dt.datetime.now(tz=dt.UTC).strftime("%Y%m%d%H%M%S")
    return f"chat_{timestamp}_{unique_id}"


def is_valid_chat_id(chat_id: str) -> bool:
    """Validate chat ID format.

    Args:
        chat_id: Chat identifier to validate

    Returns:
        bool: True if chat_id matches expected format
    """
    if not isinstance(chat_id, str):
        return False

    parts = chat_id.split("_")
    if len(parts) != 3:
        return False

    if parts[0] != "chat":
        return False

    # Validate timestamp (14 digits: YYYYMMDDHHMMSS)
    if not (parts[1].isdigit() and len(parts[1]) == 14):
        return False

    # Validate hex ID (12 hex characters)
    if not (len(parts[2]) == 12 and all(c in "0123456789abcdef" for c in parts[2])):
        return False

    return True
