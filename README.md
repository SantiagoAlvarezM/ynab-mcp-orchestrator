# YNAB MCP Orchestrator 🚀

An intelligent, LLM-agnostic **Model Context Protocol (MCP)** server that bridges bank statements and [YNAB (You Need A Budget)](https://www.ynab.com/).

The server exposes tools, resources, and prompts that allow **any MCP-compatible host** (Claude Desktop, ChatGPT, Gemini, etc.) to:

1. 📂 **List & read** bank statement files (PDF, Excel, CSV, images)
2. 🤖 **Extract** transactions using the host LLM's intelligence
3. ✅ **Validate** extracted data against a strict schema
4. 💰 **Sync** validated transactions to your YNAB budget

## 🏗 Architecture (Phase 1 — Local)

```
┌─────────────────────────────┐
│   MCP Host                  │
│   (Claude / ChatGPT /       │
│    Gemini / etc.)           │
└─────────┬───────────────────┘
          │ stdio
┌─────────▼───────────────────┐
│   YNAB MCP Server           │
│                              │
│   Tools:                     │
│   • list_bank_statements     │
│   • read_bank_statement      │
│   • validate_transactions    │
│   • list_ynab_budgets        │
│   • list_ynab_accounts       │
│   • list_ynab_categories     │
│   • list_ynab_payees         │
│   • list_ynab_transactions   │
│   • update_ynab_transactions │
│   • find_internal_transfer_candidates  │
│   • create_ynab_account      │
│   • create_ynab_category     │
│   • create_ynab_payee        │
│   • create_ynab_transactions │
│   • delete_ynab_transactions │
│   Resources:                 │
│   • Transaction Schema       │
│   • Batch Schema             │
│   • Supported Banks          │
│   • Cleanup Rules            │
│                              │
│   Prompts:                   │
│   • extract_transactions     │
│   • categorize_transactions  │
│   • process_statement        │
│   • audit_uncategorized_txns │
└──────┬──────────┬────────────┘
       │          │
  Local FS    YNAB API
  (PDFs,      (v1 REST)
   Excel,
   CSV,
   Images)
```

## 📋 Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended package manager)
- YNAB Personal Access Token ([get one here](https://app.ynab.com/settings/developer))

## ⚡ Quick Start

### 1. Clone & configure

```bash
cd ynab-mcp-orchestrator
cp .env.example .env
# Edit .env with your YNAB_PAT and STATEMENTS_DIR
```

**Optional server settings** (override in `.env` if needed):

| Variable | Default | Description |
|---|---|---|
| `YNAB_MCP_TRANSPORT` | `stdio` | Transport for `server.py`. One of `stdio`, `streamable-http`, `sse`. |
| `YNAB_MCP_LOG_LEVEL` | `ERROR` | FastMCP log level. One of `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |
| `YNAB_CLEANUP_RULES_PATH` | `~/Personal/payee_mapping.json` | Optional JSON mapping used by the cleanup-rules resource and audit prompt. |

### 2. Install dependencies

```bash
uv sync
```

### 3. Interactive AI Host (CLI)

We provide a built-in interactive terminal host (`host.py`) that uses Anthropic (Claude) or Google (Gemini) to execute agentic workflows for you. It automatically preserves your conversational context, strictly uses human-readable names instead of UUIDs, proactively suggests creation of missing categories or payees, and formats outputs beautifully using `rich` tables and color-coded JSON blocks.

Ensure you have added `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` to your `.env` file.

```bash
# Run with Claude (default)
uv run host.py

# Run with Gemini
uv run host.py --provider gemini
```

### 4. Test with MCP Inspector

```bash
uv run mcp dev server.py
```

Opens a browser-based UI at `http://localhost:6274` where you can test all tools, resources, and prompts manually.

**Troubleshooting MCP Inspector:**
If your browser shows **"Error Connecting to MCP Inspector Proxy"** or your terminal says **"PORT IS IN USE"**, an old session might be stuck in the background. Free the ports by running:
```bash
fuser -k 6277/tcp && fuser -k 6274/tcp
```
If you encounter proxy authentication issues or don't want to deal with session tokens locally, you can disable the requirement:
```bash
DANGEROUSLY_OMIT_AUTH=true uv run mcp dev server.py
```

### 5. Connect to Claude Desktop

Add to your Claude Desktop MCP config (`~/.config/claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "ynab": {
      "command": "uv",
      "args": ["--directory", "/path/to/ynab-mcp-orchestrator", "run", "server.py"]
    }
  }
}
```

## 📄 Supported File Formats

| Format | Extensions | How it works |
|--------|-----------|--------------|
| **PDF** | `.pdf` | Text extraction via pymupdf |
| **Excel** | `.xlsx`, `.xls` | All sheets read via openpyxl |
| **CSV** | `.csv` | Auto-detects encoding & delimiter |
| **Image** | `.png`, `.jpg`, `.jpeg` | Base64 for LLM vision analysis |

## 🔄 Typical Workflow

1. **"List my bank statements"** → calls `list_bank_statements`
2. **"Extract transactions from mayo_2026/davivienda.pdf"** → uses `extract_transactions` prompt
3. **"Validate these transactions"** → calls `validate_transactions`
4. **"Categorize and push to YNAB"** → uses `categorize_transactions` prompt + `create_ynab_transactions`

Or use the **`process_statement`** prompt for the full end-to-end workflow in one shot.

## 🧹 Cleanup Workflow

For existing YNAB cleanup work, the server also exposes:

- `list_ynab_transactions` to inspect current transactions with payee, category, import, and transfer-link metadata.
- `update_ynab_transactions` to apply explicit payee/category/memo/approval/cleared updates by transaction ID.
- `find_internal_transfer_candidates` to locate same-date, same-amount, opposite-sign pairs and separate already-linked transfers from ambiguous candidates.
- `ynab://cleanup/rules` for optional local mapping rules.
- `audit_uncategorized_transactions` to guide a review of missing payees/categories while ignoring normal linked-transfer category nulls.

## 🛠 Development

```bash
# Run MCP Inspector
uv run mcp dev server.py

# Run server directly (stdio)
uv run server.py
```

## 🔒 Security Features

This orchestrator is designed with strict security boundaries:
- **Path Traversal Protection:** Bank statement reads and directory listings are strictly locked to your configured `STATEMENTS_DIR`.
- **MCP Tool Annotations:** Every tool declares `readOnly` / `destructive` / `idempotent` hints, so MCP hosts can gate dangerous calls behind explicit user approval without hard-coding tool names.
- **Human-in-the-Loop:** The interactive host pauses and requires explicit terminal approval before executing any state-mutating actions (like creating or deleting YNAB transactions, accounts, payees, or categories).
- **Prompt Injection Defense:** External statement data is wrapped in strict XML delimiters to prevent malicious payloads from hijacking the LLM's instructions.
- **API Safety:** YNAB API identifiers are fully sanitized and URL-encoded.
- **Credential Redaction:** Sensitive tool parameters (like bank statement passwords) are actively redacted from the interactive console logs to prevent local leakage.

For the full threat model and how to report vulnerabilities, see [SECURITY.md](./SECURITY.md).

## 📜 License

MIT
