"""Tests for transaction models and schema generation."""

import json

import pytest
from pydantic import ValidationError

from src.models.transaction import (
    ClearedStatus,
    TransactionBatch,
    TransactionCreate,
    get_batch_schema,
    get_transaction_schema,
)


class TestTransactionCreate:
    """Tests for the TransactionCreate model."""

    def test_valid_transaction(self):
        txn = TransactionCreate(
            date="2026-05-15",
            amount=-150500,
            payee_name="Exito Envigado",
            memo="Compra TC *1234",
        )
        assert txn.date == "2026-05-15"
        assert txn.amount == -150500
        assert txn.cleared == ClearedStatus.UNCLEARED
        assert txn.approved is False

    def test_minimal_transaction(self):
        """Only date and amount are truly required."""
        txn = TransactionCreate(date="2026-05-15", amount=-50000)
        assert txn.payee_name is None
        assert txn.memo is None
        assert txn.category_id is None
        assert txn.account_id is None

    def test_missing_date_raises(self):
        with pytest.raises(ValidationError):
            TransactionCreate(amount=-50000)

    def test_missing_amount_raises(self):
        with pytest.raises(ValidationError):
            TransactionCreate(date="2026-05-15")

    def test_invalid_amount_type_raises(self):
        with pytest.raises(ValidationError):
            TransactionCreate(date="2026-05-15", amount="not-a-number")

    def test_serialization_roundtrip(self):
        txn = TransactionCreate(
            date="2026-05-15",
            amount=-150500,
            payee_name="Exito",
            cleared=ClearedStatus.UNCLEARED,
        )
        data = txn.model_dump()
        txn2 = TransactionCreate.model_validate(data)
        assert txn == txn2

    def test_json_serialization(self):
        txn = TransactionCreate(date="2026-05-15", amount=3500000)
        json_str = txn.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["date"] == "2026-05-15"
        assert parsed["amount"] == 3500000


class TestTransactionBatch:
    """Tests for the TransactionBatch model."""

    def test_empty_batch(self):
        batch = TransactionBatch(source_file="test.pdf")
        assert batch.count == 0
        assert batch.total_inflows == 0
        assert batch.total_outflows == 0

    def test_batch_with_transactions(self):
        batch = TransactionBatch(
            source_file="extracto.pdf",
            bank_name="Bancolombia",
            transactions=[
                TransactionCreate(date="2026-05-15", amount=-150500),
                TransactionCreate(date="2026-05-14", amount=3500000),
                TransactionCreate(date="2026-05-13", amount=-45900),
            ],
        )
        assert batch.count == 3
        assert batch.total_inflows == 3500000
        assert batch.total_outflows == -150500 + -45900

    def test_batch_bank_name_optional(self):
        batch = TransactionBatch(source_file="test.csv")
        assert batch.bank_name is None


class TestSchemaExport:
    """Tests for JSON schema generation."""

    def test_transaction_schema_is_valid_json_schema(self):
        schema = get_transaction_schema()
        assert "properties" in schema
        assert "date" in schema["properties"]
        assert "amount" in schema["properties"]

    def test_batch_schema_is_valid_json_schema(self):
        schema = get_batch_schema()
        assert "properties" in schema
        assert "source_file" in schema["properties"]
        assert "transactions" in schema["properties"]

    def test_schema_includes_descriptions(self):
        schema = get_transaction_schema()
        assert "description" in schema["properties"]["date"]
        assert "description" in schema["properties"]["amount"]

    def test_schema_includes_examples(self):
        schema = get_transaction_schema()
        assert "examples" in schema["properties"]["date"]
