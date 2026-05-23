# Security

This document describes the threat model the YNAB MCP Orchestrator is
designed against and the mitigations it implements. If you find a
weakness not covered here, please open a private security advisory on
GitHub rather than a public issue.

## Threat model

The orchestrator processes **untrusted third-party content** (bank
statements) and acts on a **trusted external API** (YNAB) using a
long-lived Personal Access Token. The primary risks are:

1. **Indirect prompt injection** via crafted statement content steering
   the LLM into unintended tool calls (e.g. mass deletes, false transfers).
2. **Path traversal** allowing the file-read tool to escape the
   configured statements directory and exfiltrate arbitrary files.
3. **Credential leakage** of YNAB tokens or statement passwords via
   logs, transcripts, or console output.
4. **Unauthorized destructive operations** — the LLM creating, mutating,
   or deleting YNAB entities without user awareness.

## Mitigations

### Prompt injection isolation

`read_bank_statement` wraps every text extraction in `<statement_data>`
delimiters and metadata in `<statement_metadata>` tags before returning
it to the host. The system prompt shipped with the interactive client
explicitly instructs the model to treat content inside these tags as
inert data, not instructions. See `src/tools/filesystem.py`.

### Path traversal protection

`STATEMENTS_DIR` is resolved to its canonical absolute path at config
load (`src/config.py`). Both `list_bank_statements` and
`read_bank_statement` resolve any caller-supplied path and reject
requests whose resolved path is not contained within `STATEMENTS_DIR`.
See `src/tools/filesystem.py` and `src/services/file_reader.py`.

### Credential redaction

The interactive client (`src/hosts/base.py`) redacts any tool argument
whose key contains `password` before printing it to the console. The
YNAB Personal Access Token is read from the environment at startup and
is never logged or echoed.

### Human-in-the-loop on destructive tools

Every tool that mutates YNAB state declares MCP
`ToolAnnotations(readOnlyHint=False)`. The interactive client builds
its approval set from those annotations — any tool the server marks as
not-read-only requires explicit user confirmation in the terminal
before it runs. The host application does **not** rely on a hard-coded
tool-name allowlist, so adding a new mutating tool automatically picks
up the approval gate.

### Tool error semantics

Tool failures surface via `ToolError` (FastMCP) so the host receives
`isError: true` and can react accordingly. The previous pattern of
returning `{"error": "..."}` JSON payloads (which the host could not
distinguish from successful results) has been removed.

## Out of scope

- Multi-tenant deployments. The server assumes a single trusted user.
- YNAB-side abuse. The token grants full access to your budget; treat
  it like any other production credential.
- Side-channel attacks against the host (terminal eavesdropping,
  screen capture, etc.).

## Reporting a vulnerability

Open a private security advisory at
`https://github.com/SantiagoAlvarezM/ynab-mcp-orchestrator/security/advisories/new`.
