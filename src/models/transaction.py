"""Pydantic models for YNAB transactions.

These models define the contract between the LLM extraction and the YNAB API.
The host LLM must produce JSON conforming to these schemas.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ClearedStatus(StrEnum):
    """YNAB transaction cleared status."""

    CLEARED = "cleared"
    UNCLEARED = "uncleared"
    RECONCILED = "reconciled"


class TransactionCreate(BaseModel):
    """A single transaction to create in YNAB.

    This is the target schema that the LLM must produce when extracting
    transactions from a bank statement.

    Amounts are in YNAB "milliunits" format: multiply the real amount by 1000.
    For example: $150.50 → 150500, -$42.00 → -42000.
    Outflows (expenses) are negative, inflows (income) are positive.
    """

    date: str = Field(
        description="Transaction date in ISO 8601 format: YYYY-MM-DD",
        examples=["2026-05-15"],
    )
    amount: int = Field(
        description=(
            "Amount in YNAB milliunits (amount x 1000). "
            "Negative for outflows/expenses, positive for inflows/income. "
            "Example: -150500 means an expense of $150.50"
        ),
        examples=[-150500, 2000000],
    )
    payee_name: str | None = Field(
        default=None,
        description=(
            "Payee/merchant name. YNAB will auto-match to existing payees "
            "or create new ones. Use clean, readable names."
        ),
        examples=["Exito Envigado", "Nómina Empresa"],
    )
    memo: str | None = Field(
        default=None,
        description="Combined description or memo from the bank statement",
        examples=["Compra TC *1234 - Supermercado"],
    )
    cleared: ClearedStatus = Field(
        default=ClearedStatus.UNCLEARED,
        description="Cleared status. Use 'uncleared' for imported transactions.",
    )
    approved: bool = Field(
        default=False,
        description="Whether the transaction is approved. Always False for imports.",
    )
    category_id: str | None = Field(
        default=None,
        description="YNAB category UUID. Set during categorization step.",
    )
    account_id: str | None = Field(
        default=None,
        description="YNAB account UUID where this transaction belongs.",
    )


class TransactionBatch(BaseModel):
    """A batch of transactions extracted from a single bank statement."""

    source_file: str = Field(
        description="Original filename of the bank statement",
    )
    bank_name: str | None = Field(
        default=None,
        description="Name of the bank (e.g., 'Davivienda', 'Bancolombia')",
    )
    transactions: list[TransactionCreate] = Field(
        default_factory=list,
        description="List of extracted transactions",
    )

    @property
    def total_inflows(self) -> int:
        """Sum of all positive amounts (milliunits)."""
        return sum(t.amount for t in self.transactions if t.amount > 0)

    @property
    def total_outflows(self) -> int:
        """Sum of all negative amounts (milliunits)."""
        return sum(t.amount for t in self.transactions if t.amount < 0)

    @property
    def count(self) -> int:
        return len(self.transactions)


class ValidationResult(BaseModel):
    """Result of validating a batch of transactions."""

    is_valid: bool
    total_transactions: int
    valid_count: int
    error_count: int
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StatementFile(BaseModel):
    """Metadata about a bank statement file on disk."""

    name: str
    path: str
    size_bytes: int
    extension: str
    modified_at: str


# ── Schema Export ───────────────────────────────────────────────────────────


def get_transaction_schema() -> dict:
    """Returns the JSON schema for TransactionCreate.

    This is exposed as an MCP resource so the host LLM knows
    exactly what format to produce.
    """
    return TransactionCreate.model_json_schema()


def get_batch_schema() -> dict:
    """Returns the JSON schema for TransactionBatch."""
    return TransactionBatch.model_json_schema()
