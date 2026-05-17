"""Filesystem tools — list and read bank statement files."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from pydantic import Field

from src.config import STATEMENTS_DIR, SUPPORTED_EXTENSIONS
from src.models.transaction import StatementFile
from src.services.file_reader import read_file


def list_bank_statements(
    directory: str = Field(
        default="",
        description=(
            "Optional subdirectory (e.g. month folder like 'mayo_2026') "
            "within the statements root. Leave empty to list all files."
        ),
    ),
) -> str:
    """List bank statement files available for processing.

    Scans the configured statements directory for supported file types
    (PDF, Excel, CSV, images) and returns metadata for each file.
    """
    base = STATEMENTS_DIR
    if directory:
        base = (base / directory).resolve()

    if not base.is_relative_to(STATEMENTS_DIR):
        return json.dumps(
            {
                "error": f"Invalid directory path. Must be within {STATEMENTS_DIR}",
                "statements_dir": str(STATEMENTS_DIR),
            }
        )

    if not base.exists():
        return json.dumps(
            {
                "error": f"Directory not found: {base}",
                "statements_dir": str(STATEMENTS_DIR),
                "hint": "Check STATEMENTS_DIR in .env or create the directory.",
            }
        )

    files: list[dict] = []
    # Walk recursively
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


def read_bank_statement(
    file_path: str = Field(
        description=(
            "Absolute path to the bank statement file. "
            "Supports: .pdf, .xlsx, .xls, .csv, .png, .jpg, .jpeg"
        ),
    ),
    password: str = Field(
        default="",
        description=(
            "Optional password for encrypted/protected PDF or Excel files. "
            "Colombian banks often use the last 4 digits of your ID (cédula) "
            "or document number as the password. Leave empty if not protected."
        ),
    ),
) -> str:
    """Read and extract content from a bank statement file.

    For text-based files (PDF, Excel, CSV), returns the raw text content.
    For image files, returns base64-encoded data for visual analysis
    by the host LLM's vision capabilities.

    Supports password-protected PDF and Excel files. If the file is
    protected and no password is provided, an error message will indicate
    that a password is required.

    The extracted content should then be processed using the
    'extract_transactions' prompt to produce structured transaction data.
    """
    try:
        result = read_file(file_path, password=password or None)
        # Isolate untrusted file content to prevent indirect prompt injection
        if "content" in result and result.get("type") == "text":
            result["content"] = f"<statement_data>\n{result['content']}\n</statement_data>"

        return json.dumps(result, indent=2, ensure_ascii=False)
    except FileNotFoundError as e:
        return json.dumps({"error": str(e)})
    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": f"Failed to read file: {e}"})
