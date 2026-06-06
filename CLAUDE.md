# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Package Manager

Use `uv` exclusively — no pip, poetry, or pipx.

```bash
uv sync                          # install deps (including dev group)
uv run <cmd>                     # run any command in the venv
```

## Commands

```bash
uv run ruff format .             # format
uv run ruff check --fix .        # lint + auto-fix
uv run pyright                   # type check
uv run bandit -r src/            # security scan (src/ only, not tests/)
uv run pytest -v --tb=short      # run tests
uv run mcp dev server.py         # MCP Inspector at http://localhost:6274
uv run host.py                   # interactive CLI (Claude)
uv run host.py --provider gemini # interactive CLI (Gemini)
```

**After any change to `src/`: run the full test suite before declaring done.**

## Code Style

- Ruff, line-length=100, isort with `known-first-party = ["src"]`
- Pyright for types, Bandit for security
- `asyncio_mode = "auto"` in pytest — no need for explicit `@pytest.mark.asyncio`

## Environment Variables

Required:
- `YNAB_PAT` — YNAB Personal Access Token

Optional:
- `STATEMENTS_DIR` — path to bank statement PDFs (default: `~/Personal/extractos`)
- `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` — for `host.py`
- `YNAB_MCP_LOG_LEVEL` — server log level (default: `ERROR`)

Loaded from `.env` via python-dotenv. See `.env.example`.

## YNAB API: Amounts Are Milliunits

All monetary amounts sent to YNAB must be integers in **milliunits** (value × 1000). A $12.34 transaction is `12340`. This is enforced in `src/models/transaction.py` and must be respected in any LLM prompts.

## Security Invariants

When adding or modifying tools in `src/tools/`:

1. **Path traversal**: Any file path from external input must be validated against `STATEMENTS_DIR` canonical path. See `src/tools/filesystem.py` for the pattern.
2. **Prompt injection**: Bank statement content returned to the LLM must be wrapped in `<statement_data>` / `<statement_metadata>` XML tags to isolate it from instructions.
3. **Human-in-the-loop**: Destructive tools (create/delete/modify YNAB data) must declare `Tool.Annotations.UserConfirmation` so the interactive host pauses for approval.

## Architecture

- `server.py` — FastMCP entry point; registers all tools/resources/prompts
- `src/tools/` — MCP tool implementations (filesystem, ynab, validation)
- `src/services/` — External API clients (YNAB via httpx, file readers)
- `src/models/` — Pydantic schemas
- `src/hosts/` — LLM drivers for `host.py` (add new providers here following `claude.py`/`gemini.py`)

## Git Workflow

- Feature branches + PRs only — no direct commits to `main`
- Branch naming: `feat/short-description`, `fix/short-description`, `chore/...`
