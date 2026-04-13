"""File and document intake helpers for agent runs.

Handles persistence of uploaded documents, extraction of inline `<file_content>`
tags from prompts, and assembly of multimodal user-content payloads.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

    from anthropic.types import ImageBlockParam, TextBlockParam

    from rossum_agent.agent.types import UserContent
    from rossum_agent.api.models.schemas import DocumentContent, ImageContent

logger = logging.getLogger(__name__)

_FILE_CONTENT_OPEN_TAG = '<file_content path="'
_FILE_CONTENT_CLOSE_TAG = "\n</file_content>"
_SPREADSHEET_EXTENSIONS = frozenset({".xlsx", ".xls"})


def iter_file_content_tags(text: str) -> Iterator[tuple[str, str]]:
    """Yield (filename, content) for each <file_content> tag in *text*.

    Uses plain string search instead of regex to avoid ReDoS on untrusted input.
    """
    pos = 0
    while True:
        start = text.find(_FILE_CONTENT_OPEN_TAG, pos)
        if start == -1:
            break
        path_start = start + len(_FILE_CONTENT_OPEN_TAG)
        quote_end = text.find('">', path_start)
        if quote_end == -1:
            break
        filename = Path(text[path_start:quote_end]).name
        content_start = quote_end + len('">\n')
        close = text.find(_FILE_CONTENT_CLOSE_TAG, content_start)
        if close == -1:
            break
        content = text[content_start:close]
        yield filename, content
        pos = close + len(_FILE_CONTENT_CLOSE_TAG)


def sanitize_filename(raw_name: str) -> str:
    """Return a safe filename derived from untrusted input.

    Keeps only the basename and replaces path separators and other
    potentially problematic characters with underscores.
    """
    # Take only the final path component to avoid traversal and embedded dirs.
    name = Path(raw_name).name
    # Replace any remaining path separators and whitespace/control chars.
    safe_chars = []
    for ch in name:
        if ch.isalnum() or ch in {".", "-", "_"}:
            safe_chars.append(ch)
        else:
            safe_chars.append("_")
    sanitized = "".join(safe_chars).strip("._")
    return sanitized or "file"


def save_documents_to_output_dir(documents: list[DocumentContent], output_dir: Path) -> None:
    resolved_output_dir = output_dir.resolve()
    for doc in documents:
        safe_name = Path(doc.filename).name
        if not safe_name or safe_name in {".", ".."}:
            logger.error(f"Path traversal blocked for document: {doc.filename}")
            continue
        # safe_name is a single path component (Path.name strips dirs),
        # so the join cannot escape resolved_output_dir.
        file_path = resolved_output_dir / safe_name
        try:
            file_data = base64.b64decode(doc.data)
            file_path.write_bytes(file_data)
            logger.info(f"Saved document to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save document {doc.filename}: {e}")


def extract_and_save_text_files(prompt: str, output_dir: Path) -> list[Path]:
    """Extract text files from <file_content> tags in the prompt and save to output dir.

    Skips spreadsheet files (passed by path, not content).
    Returns list of saved file paths.
    """
    saved_paths: list[Path] = []
    resolved_output_dir = output_dir.resolve()
    for filename, content in iter_file_content_tags(prompt):
        if Path(filename).suffix.lower() in _SPREADSHEET_EXTENSIONS:
            continue
        safe_name = Path(sanitize_filename(filename)).name
        if not safe_name or safe_name in {".", ".."}:
            logger.error(f"Path traversal blocked for text file: {filename}")
            continue
        # Build path from resolved base + sanitized single-component name.
        # safe_name is guaranteed to contain no separators (sanitize_filename
        # strips them), so the join cannot escape resolved_output_dir.
        file_path = resolved_output_dir / safe_name
        try:
            file_path.write_text(content, encoding="utf-8")
            saved_paths.append(file_path)
            logger.info(f"Saved text file to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save text file {filename}: {e}")
    return saved_paths


def build_user_content(
    prompt: str,
    images: list[ImageContent] | None,
    documents: list[DocumentContent] | None = None,
    output_dir: Path | None = None,
    text_file_paths: list[Path] | None = None,
) -> UserContent:
    if not images and not documents and not text_file_paths:
        return prompt

    content: list[ImageBlockParam | TextBlockParam] = []
    if images:
        for img in images:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": img.media_type,
                        "data": img.data,
                    },
                }
            )
    if documents and output_dir:
        text_media_types = {"text/plain", "text/markdown"}
        inlineable_docs = [d for d in documents if d.media_type in text_media_types]
        other_docs = [d for d in documents if d.media_type not in text_media_types]
        if inlineable_docs:
            inlined = []
            for doc in inlineable_docs:
                text = base64.b64decode(doc.data).decode("utf-8")
                inlined.append(f'<file_content path="{doc.filename}">\n{text}\n</file_content>')
            content.append({"type": "text", "text": "\n\n".join(inlined)})
        if other_docs:
            doc_paths = [str(output_dir / Path(doc.filename).name) for doc in other_docs]
            doc_info = "\n".join(f"- {path}" for path in doc_paths)
            content.append({"type": "text", "text": f"[Uploaded documents available for processing:\n{doc_info}]"})
    if text_file_paths:
        paths_info = "\n".join(f"- {path}" for path in text_file_paths)
        content.append(
            {
                "type": "text",
                "text": f"[Text files saved to workspace — readable via open() in execute_python:\n{paths_info}]",
            }
        )
    content.append({"type": "text", "text": prompt})
    return content
