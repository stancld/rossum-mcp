import os
from pathlib import Path

# Output directory for generated files
OUTPUT_DIR = Path("./outputs")


def get_generated_files() -> list[str]:
    """Get list of files in the outputs directory."""
    if not OUTPUT_DIR.exists():
        return []

    return [str(f.resolve()) for f in OUTPUT_DIR.iterdir() if f.is_file()]


def get_generated_files_with_metadata() -> dict[str, float]:
    """Get files in the outputs directory with their modification times."""
    if not OUTPUT_DIR.exists():
        return {}

    return {str(f.resolve()): f.stat().st_mtime for f in OUTPUT_DIR.iterdir() if f.is_file()}


def clear_generated_files() -> None:
    """Delete all files in the outputs directory."""
    if not OUTPUT_DIR.exists():
        return

    for file_path in OUTPUT_DIR.iterdir():
        if file_path.is_file():
            file_path.unlink()


def check_env_vars() -> list[tuple[str, str]]:
    """Check if required environment variables are set.

    For Bedrock models (LLM_MODEL_ID starting with 'bedrock/'), only LLM_MODEL_ID is required.
    For OpenAI-compatible models, LLM_API_BASE_URL is also required.
    """
    # Always required
    required_vars = {
        "ROSSUM_API_TOKEN": "Rossum API authentication token",
        "ROSSUM_API_BASE_URL": "Rossum API base URL",
    }

    missing = []
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing.append((var, description))

    # Check LLM configuration
    if (model_id := os.getenv("LLM_MODEL_ID")) and not model_id.startswith("bedrock/"):  # noqa: SIM102
        # For non-Bedrock models, LLM_API_BASE_URL is required
        if not os.getenv("LLM_API_BASE_URL"):
            missing.append(("LLM_API_BASE_URL", "LLM API endpoint URL (required for non-Bedrock models)"))

    return missing
