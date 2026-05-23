"""Validation tool — validate extracted transactions against the schema."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from src.models.transaction import (
    TransactionCreate,
    ValidationResult,
)


def validate_transactions(transactions: list[dict[str, Any]]) -> str:
    """Validate extracted transactions against the YNAB transaction schema.

    Returns a ValidationResult JSON with detailed errors and warnings.
    Use this before calling create_ynab_transactions to iterate on errors
    without invoking the destructive create.
    """
    errors: list[str] = []
    warnings: list[str] = []
    valid_count = 0
    total = len(transactions)

    for i, txn_data in enumerate(transactions):
        idx = i + 1
        try:
            txn = TransactionCreate.model_validate(txn_data)
            valid_count += 1
            _semantic_checks(txn, idx, warnings)
        except ValidationError as e:
            for err in e.errors():
                field = " -> ".join(str(loc) for loc in err["loc"])
                errors.append(f"Transaction {idx}: {field} - {err['msg']}")

    result = ValidationResult(
        is_valid=len(errors) == 0,
        total_transactions=total,
        valid_count=valid_count,
        error_count=len(errors),
        errors=errors,
        warnings=warnings,
    )
    return json.dumps(result.model_dump(), indent=2)


def _semantic_checks(txn: TransactionCreate, idx: int, warnings: list[str]) -> None:
    """Run additional semantic validations beyond schema conformance."""
    try:
        dt = datetime.strptime(txn.date, "%Y-%m-%d")
        if dt.year < 2020 or dt.year > 2030:
            warnings.append(f"Transaction {idx}: date '{txn.date}' has an unusual year.")
    except ValueError:
        warnings.append(f"Transaction {idx}: date '{txn.date}' is not in YYYY-MM-DD format.")

    if txn.amount == 0:
        warnings.append(f"Transaction {idx}: amount is zero.")

    if not txn.payee_name:
        warnings.append(f"Transaction {idx}: no payee_name set. YNAB will show this as 'No Payee'.")

    if not txn.account_id:
        warnings.append(
            f"Transaction {idx}: no account_id set. You must set this before pushing to YNAB."
        )
