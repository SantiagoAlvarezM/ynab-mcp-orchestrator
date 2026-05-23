"""Filesystem tools — list and read bank statement files."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from mcp.server.fastmcp.exceptions import ToolError

from src.config import STATEMENTS_DIR, SUPPORTED_EXTENSIONS
from src.models.transaction import StatementFile
from src.services.file_reader import read_file


def list_bank_statements(directory: str = "") -> str:
    """List bank statement files available for processing.

    Scans the configured statements directory for supported file types
    (PDF, Excel, CSV, images) and returns metadata for each file.
    """
    base = STATEMENTS_DIR
    if directory:
        base = (base / directory).resolve()

    if not base.is_relative_to(STATEMENTS_DIR):
        raise ToolError(
            f"Invalid directory path: '{directory}' resolves outside the configured "
            f"statements root ({STATEMENTS_DIR})."
        )

    if not base.exists():
        raise ToolError(
            f"Directory not found: {base}. Check STATEMENTS_DIR in .env "
            "or create the directory first."
        )

    files: list[dict] = []
    for file_path in sorted(base.rglob("*")):
        if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
            stat = file_path.stat()
            sf = StatementFile(
                name=file_path.name,
                path=str(file_path),
                size_bytes=stat.st_size,
                extension=file_path.suffix.lower(),
                modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
            )
            files.append(sf.model_dump())

    return json.dumps(
        {
            "directory": str(base),
            "total_files": len(files),
            "files": files,
        },
        indent=2,
        ensure_ascii=False,
    )


def read_bank_statement(file_path: str, password: str = "") -> str:
    """Read and extract content from a bank statement file.

    For text-based files (PDF, Excel, CSV), returns the raw text content.
    For image files, returns base64-encoded data for visual analysis
    by the host LLM's vision capabilities.

    Supports password-protected PDF and Excel files. If the file is
    protected and no password is provided, the tool raises an error
    indicating that a password is required.

    The extracted content should then be processed using the
    'extract_transactions' prompt to produce structured transaction data.
    """
    try:
        result = read_file(file_path, password=password or None)
    except FileNotFoundError as e:
        raise ToolError(str(e)) from e
    except PermissionError as e:
        raise ToolError(str(e)) from e
    except ValueError as e:
        raise ToolError(str(e)) from e
    except Exception as e:
        raise ToolError(f"Failed to read file: {e}") from e

    # Isolate untrusted file content to prevent indirect prompt injection
    if "content" in result and result.get("type") == "text":
        result["content"] = f"<statement_data>\n{result['content']}\n</statement_data>"

    return json.dumps(result, indent=2, ensure_ascii=False)
