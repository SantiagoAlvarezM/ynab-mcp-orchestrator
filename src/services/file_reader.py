"""Multi-format bank statement file reader.

Supports:
  - PDF  (.pdf)         → raw text via pymupdf (password-protected supported)
  - Excel (.xlsx, .xls) → tabular text via openpyxl + msoffcrypto (password-protected supported)
  - CSV  (.csv)         → raw CSV content
  - Image (.png, .jpg)  → base64-encoded data for LLM vision
"""

from __future__ import annotations

import base64
import csv
import io
import mimetypes
from pathlib import Path

import fitz  # pymupdf
import msoffcrypto
import openpyxl

from src.config import STATEMENTS_DIR

# ── Public API ──────────────────────────────────────────────────────────────


def read_file(file_path: str | Path, password: str | None = None) -> dict:
    """Read a bank statement file and return its content.

    Args:
        file_path: Path to the file.
        password: Optional password for encrypted PDF/Excel files.

    Returns a dict with keys:
      - type: "text" or "image"
      - content: the extracted text, OR base64-encoded image data
      - mime_type: MIME type of the original file
      - file_name: basename of the file
      - pages: number of pages/sheets (for PDF/Excel, None otherwise)
      - password_protected: whether the file required a password

    For images, the dict also includes:
      - data: base64-encoded image bytes
    """
    path = Path(file_path).resolve()

    if not path.is_relative_to(STATEMENTS_DIR):
        raise PermissionError(
            f"Access denied: '{path}' is outside the allowed statements directory."
        )

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    ext = path.suffix.lower()
    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"

    readers = {
        ".pdf": _read_pdf,
        ".xlsx": _read_excel,
        ".xls": _read_excel,
        ".csv": _read_csv,
        ".png": _read_image,
        ".jpg": _read_image,
        ".jpeg": _read_image,
    }

    reader = readers.get(ext)
    if reader is None:
        raise ValueError(
            f"Unsupported file format: '{ext}'. Supported: {', '.join(sorted(readers.keys()))}"
        )

    result = reader(path, password)
    result["file_name"] = path.name
    result["mime_type"] = mime
    return result


# ── Readers ─────────────────────────────────────────────────────────────────


def _read_pdf(path: Path, password: str | None = None) -> dict:
    """Extract all text from a PDF using pymupdf. Supports password-protected PDFs."""
    doc = fitz.open(str(path))
    was_protected = False

    if doc.needs_pass:
        was_protected = True
        if not password:
            doc.close()
            raise ValueError(
                f"PDF '{path.name}' is password-protected. "
                "Please provide the password using the 'password' parameter."
            )
        auth_result = doc.authenticate(password)
        if auth_result == 0:
            doc.close()
            raise ValueError(
                f"Incorrect password for PDF '{path.name}'. "
                "Please check the password and try again."
            )

    pages = []
    for page_num, page in enumerate(doc, start=1):  # type: ignore
        text = page.get_text("text")
        if text.strip():
            pages.append(f"--- Page {page_num} ---\n{text}")
    doc.close()

    return {
        "type": "text",
        "content": "\n\n".join(pages) if pages else "(No text content found in PDF)",
        "pages": len(pages),
        "password_protected": was_protected,
    }


def _read_excel(path: Path, password: str | None = None) -> dict:
    """Read an Excel file and convert all sheets to tab-separated text.

    Supports password-protected Excel files via msoffcrypto-tool.
    """
    was_protected = False
    source = str(path)

    # Try to detect and decrypt password-protected Excel files
    if password:
        try:
            decrypted = io.BytesIO()
            with open(path, "rb") as f:
                office_file = msoffcrypto.OfficeFile(f)
                if office_file.is_encrypted():
                    was_protected = True
                    office_file.load_key(password=password)
                    office_file.decrypt(decrypted)
                    decrypted.seek(0)
                    source = decrypted
        except Exception as e:
            raise ValueError(
                f"Failed to decrypt Excel file '{path.name}': {e}. "
                "Please check the password and try again."
            ) from e
    else:
        # Check if encrypted without a password
        try:
            with open(path, "rb") as f:
                office_file = msoffcrypto.OfficeFile(f)
                if office_file.is_encrypted():
                    raise ValueError(
                        f"Excel file '{path.name}' is password-protected. "
                        "Please provide the password using the 'password' parameter."
                    )
        except msoffcrypto.exceptions.FileFormatError:
            # Not an OLE file or not encrypted, proceed normally
            pass

    wb = openpyxl.load_workbook(source, read_only=True, data_only=True)
    sheets_text = []

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = []
        for row in ws.iter_rows(values_only=True):
            # Convert each cell to string, handle None
            cells = [str(cell) if cell is not None else "" for cell in row]
            rows.append("\t".join(cells))

        if rows:
            sheets_text.append(f"--- Sheet: {sheet_name} ---\n" + "\n".join(rows))

    wb.close()

    return {
        "type": "text",
        "content": "\n\n".join(sheets_text) if sheets_text else "(Empty workbook)",
        "pages": len(sheets_text),
        "password_protected": was_protected,
    }


def _read_csv(path: Path, password: str | None = None) -> dict:
    """Read a CSV file and return its raw content."""
    # CSV files are never password-protected
    raw_bytes = path.read_bytes()

    # Try UTF-8 first, fall back to latin-1
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            text = raw_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw_bytes.decode("utf-8", errors="replace")

    # Detect delimiter
    try:
        sample = text[:4096]
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","

    # Re-format as clean TSV for consistency with Excel output
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = []
    for row in reader:
        rows.append("\t".join(row))

    return {
        "type": "text",
        "content": "\n".join(rows) if rows else "(Empty CSV file)",
        "pages": None,
        "password_protected": False,  # nosec B105
    }


def _read_image(path: Path, password: str | None = None) -> dict:
    """Read an image file and return base64-encoded content for LLM vision."""
    image_bytes = path.read_bytes()
    b64_data = base64.b64encode(image_bytes).decode("ascii")

    return {
        "type": "image",
        "data": b64_data,
        "size_bytes": len(image_bytes),
        "pages": None,
        "password_protected": False,  # nosec B105
    }
