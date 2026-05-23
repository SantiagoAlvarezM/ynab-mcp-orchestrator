"""YNAB MCP Orchestrator — MCP Server Entry Point.

An intelligent MCP server that bridges bank statements and YNAB.
Exposes tools, resources, and prompts for the full extraction-to-sync workflow.

Usage:
    # Run with MCP Inspector for testing
    uv run mcp dev server.py

    # Run directly (stdio transport)
    uv run server.py
"""

import json
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts import base
from mcp.types import ContentBlock
from pydantic import Field

from src.config import STATEMENTS_DIR
from src.models.transaction import get_batch_schema, get_transaction_schema
from src.tools.filesystem import list_bank_statements, read_bank_statement
from src.tools.validation import validate_transactions
from src.tools.ynab import (
    create_ynab_account,
    create_ynab_category,
    create_ynab_payee,
    create_ynab_transactions,
    delete_ynab_transactions,
    get_ynab_payees,
    list_ynab_accounts,
    list_ynab_budgets,
    list_ynab_categories,
)

# ── Server Instance ─────────────────────────────────────────────────────────

mcp = FastMCP(
    "YNAB MCP Orchestrator",
    log_level="ERROR",
)


# ═══════════════════════════════════════════════════════════════════════════
# TOOLS
# ═══════════════════════════════════════════════════════════════════════════


@mcp.tool(
    name="list_bank_statements",
    description=(
        "List bank statement files (PDF, Excel, CSV, images) in the "
        "configured statements directory. Optionally filter by subdirectory."
    ),
)
def tool_list_bank_statements(
    directory: str = Field(
        default="",
        description=(
            "Optional subdirectory (e.g. 'mayo_2026') within the statements root. "
            "Leave empty to list all files recursively."
        ),
    ),
) -> str:
    return list_bank_statements(directory)


@mcp.tool(
    name="read_bank_statement",
    description=(
        "Read and extract content from a bank statement file. "
        "Returns a TextContent block for PDF/Excel/CSV, or TextContent + "
        "ImageContent for images so the host vision model can read them natively. "
        "Supports password-protected PDF and Excel files. "
        "Use the 'extract_transactions' prompt to process the extracted content."
    ),
)
def tool_read_bank_statement(
    file_path: str = Field(
        description="Absolute path to the bank statement file.",
    ),
    password: str = Field(
        default="",
        description=(
            "Password for encrypted PDF/Excel files. "
            "Colombian banks often use the last 4 digits of your cédula. "
            "Leave empty if the file is not password-protected."
        ),
    ),
) -> list[ContentBlock]:
    return read_bank_statement(file_path, password)


@mcp.tool(
    name="validate_transactions",
    description=(
        "Validate extracted transactions against the YNAB schema. "
        "Call this BEFORE create_ynab_transactions to catch structural errors and "
        "surface semantic warnings (zero amounts, missing account_id, unusual dates)."
    ),
)
def tool_validate_transactions(
    transactions: list[dict[str, Any]] = Field(
        description=(
            "Array of transaction objects to validate. Each object should match "
            "the schema exposed at resource ynab://schema/transaction."
        ),
    ),
) -> str:
    return validate_transactions(transactions)


@mcp.tool(
    name="list_ynab_budgets",
    description="List all YNAB budgets accessible with the configured token.",
)
async def tool_list_ynab_budgets() -> str:
    return await list_ynab_budgets()


@mcp.tool(
    name="list_ynab_accounts",
    description=(
        "List all accounts in a YNAB budget. Returns account ID, name, type, and balance."
    ),
)
async def tool_list_ynab_accounts(
    budget_id: str = Field(description="YNAB budget UUID"),
) -> str:
    return await list_ynab_accounts(budget_id)


@mcp.tool(
    name="list_ynab_categories",
    description=(
        "List all category groups and categories in a YNAB budget. "
        "Use category_id when categorizing transactions."
    ),
)
async def tool_list_ynab_categories(
    budget_id: str = Field(description="YNAB budget UUID"),
) -> str:
    return await list_ynab_categories(budget_id)


@mcp.tool(
    name="get_ynab_payees",
    description=(
        "List all payees in a YNAB budget. Useful for matching extracted names to existing payees."
    ),
)
async def tool_get_ynab_payees(
    budget_id: str = Field(description="YNAB budget UUID"),
) -> str:
    return await get_ynab_payees(budget_id)


@mcp.tool(
    name="create_ynab_transactions",
    description=(
        "Push transactions to a YNAB budget. "
        "Each transaction MUST include account_id, date, and amount. "
        "Call validate_transactions first to catch errors."
    ),
)
async def tool_create_ynab_transactions(
    budget_id: str = Field(description="YNAB budget UUID"),
    transactions: list[dict[str, Any]] = Field(
        description=(
            "Array of transaction objects to create. See resource "
            "ynab://schema/transaction for the expected per-item shape."
        ),
    ),
) -> str:
    return await create_ynab_transactions(budget_id, transactions)


@mcp.tool(
    name="delete_ynab_transactions",
    description="Delete or rollback transactions in YNAB using their IDs.",
)
async def tool_delete_ynab_transactions(
    budget_id: str = Field(description="YNAB budget UUID"),
    transaction_ids: list[str] = Field(
        description="Array of YNAB transaction UUIDs to delete.",
    ),
) -> str:
    return await delete_ynab_transactions(budget_id, transaction_ids)


YnabAccountType = Literal[
    "checking",
    "savings",
    "cash",
    "creditCard",
    "lineOfCredit",
    "otherAsset",
    "otherLiability",
    "mortgage",
    "autoLoan",
    "studentLoan",
    "personalLoan",
    "medicalDebt",
    "otherDebt",
]


@mcp.tool(
    name="create_ynab_account",
    description="Create a new account in a YNAB budget.",
)
async def tool_create_ynab_account(
    budget_id: str = Field(description="YNAB budget UUID"),
    name: str = Field(description="Name of the new account"),
    account_type: YnabAccountType = Field(
        description="YNAB account type. Must be one of the allowed values.",
    ),
    balance: int = Field(default=0, description="Initial balance in milliunits"),
) -> str:
    return await create_ynab_account(budget_id, name, account_type, balance)


@mcp.tool(
    name="create_ynab_category",
    description="Create a new category in a YNAB budget.",
)
async def tool_create_ynab_category(
    budget_id: str = Field(description="YNAB budget UUID"),
    name: str = Field(description="Name of the new category"),
    category_group_id: str = Field(description="UUID of the category group to place this in"),
) -> str:
    return await create_ynab_category(budget_id, name, category_group_id)


@mcp.tool(
    name="create_ynab_payee",
    description="Create a new payee in a YNAB budget.",
)
async def tool_create_ynab_payee(
    budget_id: str = Field(description="YNAB budget UUID"),
    name: str = Field(description="Name of the new payee"),
) -> str:
    return await create_ynab_payee(budget_id, name)


# ═══════════════════════════════════════════════════════════════════════════
# RESOURCES
# ═══════════════════════════════════════════════════════════════════════════


@mcp.resource(
    "ynab://schema/transaction",
    name="Transaction Schema",
    description=(
        "JSON Schema defining the transaction format that the LLM must produce "
        "when extracting transactions from bank statements. "
        "Amounts are in YNAB milliunits (amount x 1000)."
    ),
    mime_type="application/json",
)
def resource_transaction_schema() -> str:
    schema = get_transaction_schema()
    return json.dumps(schema, indent=2)


@mcp.resource(
    "ynab://schema/batch",
    name="Transaction Batch Schema",
    description="JSON Schema for a batch of transactions from a single bank statement.",
    mime_type="application/json",
)
def resource_batch_schema() -> str:
    schema = get_batch_schema()
    return json.dumps(schema, indent=2)


@mcp.resource(
    "ynab://banks/supported",
    name="Supported Banks & File Formats",
    description="List of supported bank statement formats and file types.",
    mime_type="application/json",
)
def resource_supported_banks() -> str:
    info = {
        "supported_file_types": {
            "pdf": {
                "extensions": [".pdf"],
                "description": "PDF bank statements — text is extracted automatically",
            },
            "excel": {
                "extensions": [".xlsx", ".xls"],
                "description": "Excel spreadsheet statements — all sheets are read",
            },
            "csv": {
                "extensions": [".csv"],
                "description": "CSV exports — auto-detects encoding and delimiter",
            },
            "image": {
                "extensions": [".png", ".jpg", ".jpeg"],
                "description": (
                    "Image-based statements — returned as base64 for LLM vision. "
                    "Requires a multimodal LLM (Claude, GPT-4o, Gemini)."
                ),
            },
        },
        "known_banks": [
            {
                "name": "Davivienda",
                "country": "Colombia",
                "common_formats": ["pdf", "xls"],
            },
            {
                "name": "Bancolombia",
                "country": "Colombia",
                "common_formats": ["pdf", "xlsx", "csv"],
            },
            {
                "name": "Nequi",
                "country": "Colombia",
                "common_formats": ["pdf", "csv"],
            },
            {
                "name": "Nu Colombia",
                "country": "Colombia",
                "common_formats": ["pdf", "csv"],
            },
        ],
        "statements_directory": str(STATEMENTS_DIR),
    }
    return json.dumps(info, indent=2, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════════
# PROMPTS
# ═══════════════════════════════════════════════════════════════════════════


@mcp.prompt(
    name="extract_transactions",
    description=(
        "Extract transactions from a bank statement. "
        "Reads the file, provides the transaction schema, and guides "
        "the LLM to produce structured JSON."
    ),
)
def prompt_extract_transactions(
    file_path: str = Field(description="Path to the bank statement file"),
    bank_name: str = Field(
        description="Name of the bank (e.g. 'Davivienda', 'Bancolombia')",
    ),
) -> list[base.Message]:
    schema = json.dumps(get_transaction_schema(), indent=2)

    prompt = f"""\
You are a financial data extraction specialist. Your task is to extract ALL
transactions from a bank statement and return them as structured JSON.

## Instructions

1. First, use the `read_bank_statement` tool with file_path="{file_path}" to
   get the statement content.

2. Analyze the content carefully. The statement is from **{bank_name}**.

3. For EACH transaction found, extract:
   - **date**: Convert to ISO 8601 format (YYYY-MM-DD)
   - **amount**: Convert to YNAB milliunits (multiply by 1000).
     Expenses/debits are NEGATIVE, income/credits are POSITIVE.
   - **payee_name**: The merchant/payee name, cleaned up for readability
   - **memo**: Any additional description or reference numbers

4. Return the result as a JSON object matching this schema:

<transaction_schema>
{schema}
</transaction_schema>

## Rules
- Do NOT skip any transactions — extract ALL of them
- Dates from Colombian banks are typically DD/MM/YYYY — convert to YYYY-MM-DD
- Amounts may use dot (.) or comma (,) as decimal separator — handle both
- Currency is Colombian Pesos (COP) unless stated otherwise
- Set cleared="uncleared" and approved=false for all transactions
- Do NOT set account_id or category_id yet — those come later

## Output Format
Return ONLY a valid JSON array of transaction objects. No extra text.
"""

    return [base.UserMessage(prompt)]


@mcp.prompt(
    name="categorize_transactions",
    description=(
        "Categorize a batch of transactions using YNAB categories. "
        "Fetches available categories and guides the LLM to assign them."
    ),
)
def prompt_categorize_transactions(
    budget_id: str = Field(description="YNAB budget UUID"),
    transactions_json: str = Field(
        description="JSON array of transactions to categorize",
    ),
) -> list[base.Message]:
    prompt = f"""\
You are a financial categorization specialist. Your task is to assign YNAB
categories to a batch of transactions.

## Instructions

1. First, use the `list_ynab_categories` tool with budget_id="{budget_id}"
   to see all available categories.

2. Review the following transactions:

<transactions>
{transactions_json}
</transactions>

3. For EACH transaction, determine the most appropriate category based on
   the payee name and memo. Assign the `category_id` field.

## Categorization Guidelines
- Supermarkets/grocery stores → Groceries
- Restaurants/cafés → Dining Out
- Uber/DiDi/transport → Transportation
- Netflix/Spotify/subscriptions → Subscriptions
- Pharmacy/health → Healthcare
- ATM withdrawals → can leave uncategorized
- Salary/income → Income categories
- If unsure, leave category_id as null

## Output Format
Return the COMPLETE transactions array with category_id populated where
applicable. Return ONLY valid JSON, no extra text.
"""

    return [base.UserMessage(prompt)]


@mcp.prompt(
    name="process_statement",
    description=(
        "Full end-to-end workflow: extract transactions from a bank statement, "
        "validate, categorize, and push to YNAB."
    ),
)
def prompt_process_statement(
    file_path: str = Field(description="Path to the bank statement file"),
    bank_name: str = Field(description="Name of the bank (e.g. 'Davivienda', 'Bancolombia')"),
    budget_id: str = Field(description="YNAB budget UUID"),
    account_id: str = Field(description="YNAB account UUID for these transactions"),
) -> list[base.Message]:
    schema = json.dumps(get_transaction_schema(), indent=2)

    prompt = f"""\
You are a financial data processing assistant. Your task is to extract
transactions from a bank statement and push them to YNAB. Follow these
steps IN ORDER:

## Step 1: Read the Statement
Use `read_bank_statement` with file_path="{file_path}"

## Step 2: Extract Transactions
From the statement content (bank: **{bank_name}**), extract ALL transactions
into this schema:

<transaction_schema>
{schema}
</transaction_schema>

Rules:
- Dates: Convert DD/MM/YYYY → YYYY-MM-DD
- Amounts: Multiply by 1000 for milliunits. Expenses are negative.
- Set account_id="{account_id}" on every transaction
- Set cleared="uncleared" and approved=false

## Step 3: Validate
Call `validate_transactions` with the extracted transactions array.
If there are errors, fix them and re-validate.

## Step 4: Categorize
Use `list_ynab_categories` with budget_id="{budget_id}" to see categories.
Assign category_id to each transaction based on the payee/memo.

## Step 5: Push to YNAB
Call `create_ynab_transactions` with budget_id="{budget_id}" and the
final `transactions` array.

## Step 6: Report
Summarize what was done:
- Total transactions extracted
- Total inflows and outflows (in human-readable COP format)
- Any warnings or skipped items
- Transaction IDs created in YNAB
"""

    return [base.UserMessage(prompt)]


# ═══════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════


def main() -> None:
    """Console script entry point — runs the MCP server over stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
