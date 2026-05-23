"""Configuration module for YNAB MCP Orchestrator."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Filesystem ──────────────────────────────────────────────────────────────

STATEMENTS_DIR = Path(
    os.getenv("STATEMENTS_DIR", os.path.expanduser("~/Personal/extractos"))
).resolve()

# Supported file extensions for bank statements
SUPPORTED_EXTENSIONS: set[str] = {
    ".pdf",
    ".xlsx",
    ".xls",
    ".csv",
    ".png",
    ".jpg",
    ".jpeg",
}

# ── YNAB API ────────────────────────────────────────────────────────────────

YNAB_BASE_URL: str = os.getenv("YNAB_BASE_URL", "https://api.ynab.com/v1")
YNAB_PAT: str = os.getenv("YNAB_PAT", "")
