"""Validation tool — validate extracted transactions against the schema."""

from __future__ import annotations

import json
from datetime import datetime

from pydantic import ValidationError

from src.models.transaction import (
    TransactionCreate,
    ValidationResult,
)


def validate_transactions(
    transactions_json: str,
) -> str:
    """Validate a list of extracted transactions against the YNAB schema.

    Accepts a JSON string representing either:
    - A TransactionBatch object (with source_file, bank_name, transactions)
    - A plain JSON array of transaction objects

    Returns a ValidationResult with details about valid/invalid transactions
    and specific error messages for any that fail validation.

    Use this BEFORE calling create_ynab_transactions to catch errors early.
    """
    errors: list[str] = []
    warnings: list[str] = []
    valid_count = 0

    try:
        data = json.loads(transactions_json)
    except json.JSONDecodeError as e:
        result = ValidationResult(
            is_valid=False,
            total_transactions=0,
            valid_count=0,
            error_count=1,
            errors=[f"Invalid JSON: {e}"],
        )
        return json.dumps(result.model_dump(), indent=2)

    # Accept both a batch object and a plain list
    if isinstance(data, dict) and "transactions" in data:
        txn_list = data["transactions"]
    elif isinstance(data, list):
        txn_list = data
    else:
        result = ValidationResult(
            is_valid=False,
            total_transactions=0,
            valid_count=0,
            error_count=1,
            errors=[
                "Expected a JSON array of transactions or an object with a 'transactions' key."
            ],
        )
        return json.dumps(result.model_dump(), indent=2)

    total = len(txn_list)

    for i, txn_data in enumerate(txn_list):
        idx = i + 1
        try:
            txn = TransactionCreate.model_validate(txn_data)
            valid_count += 1

            # Additional semantic checks
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
