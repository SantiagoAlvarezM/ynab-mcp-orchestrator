"""Tests for the transaction validation tool."""

import json

from src.tools.validation import validate_transactions


class TestValidTransactions:
    """Tests for validating correct transactions."""

    def test_valid_transactions_pass(self, valid_transactions_json):
        result_json = validate_transactions(valid_transactions_json)
        result = json.loads(result_json)
        assert result["is_valid"] is True
        assert result["total_transactions"] == 2
        assert result["valid_count"] == 2
        assert result["error_count"] == 0

    def test_single_valid_transaction(self):
        txn = json.dumps(
            [
                {
                    "date": "2026-05-15",
                    "amount": -50000,
                    "payee_name": "Test",
                    "account_id": "abc-123",
                }
            ]
        )
        result = json.loads(validate_transactions(txn))
        assert result["is_valid"] is True
        assert result["valid_count"] == 1

    def test_accepts_batch_format(self):
        batch = json.dumps(
            {
                "source_file": "test.pdf",
                "transactions": [
                    {"date": "2026-05-15", "amount": -50000, "account_id": "x"},
                ],
            }
        )
        result = json.loads(validate_transactions(batch))
        assert result["is_valid"] is True


class TestInvalidTransactions:
    """Tests for detecting invalid transactions."""

    def test_missing_required_fields(self, invalid_transactions_json):
        result_json = validate_transactions(invalid_transactions_json)
        result = json.loads(result_json)
        assert result["is_valid"] is False
        assert result["error_count"] > 0
        assert len(result["errors"]) > 0

    def test_invalid_json_input(self):
        result = json.loads(validate_transactions("not valid json{"))
        assert result["is_valid"] is False
        assert "Invalid JSON" in result["errors"][0]

    def test_wrong_structure(self):
        result = json.loads(validate_transactions(json.dumps({"foo": "bar"})))
        assert result["is_valid"] is False
        assert "Expected" in result["errors"][0]

    def test_empty_list(self):
        result = json.loads(validate_transactions(json.dumps([])))
        assert result["is_valid"] is True
        assert result["total_transactions"] == 0


class TestSemanticWarnings:
    """Tests for semantic validation warnings."""

    def test_warns_on_missing_payee(self):
        txn = json.dumps(
            [
                {
                    "date": "2026-05-15",
                    "amount": -50000,
                    "account_id": "abc",
                }
            ]
        )
        result = json.loads(validate_transactions(txn))
        assert result["is_valid"] is True  # still valid
        warnings = result["warnings"]
        assert any("payee_name" in w for w in warnings)

    def test_warns_on_missing_account_id(self):
        txn = json.dumps(
            [
                {
                    "date": "2026-05-15",
                    "amount": -50000,
                    "payee_name": "Test",
                }
            ]
        )
        result = json.loads(validate_transactions(txn))
        assert any("account_id" in w for w in result["warnings"])

    def test_warns_on_zero_amount(self):
        txn = json.dumps(
            [
                {
                    "date": "2026-05-15",
                    "amount": 0,
                    "payee_name": "Test",
                    "account_id": "abc",
                }
            ]
        )
        result = json.loads(validate_transactions(txn))
        assert any("zero" in w for w in result["warnings"])

    def test_warns_on_bad_date_format(self):
        txn = json.dumps(
            [
                {
                    "date": "15/05/2026",  # DD/MM/YYYY instead of YYYY-MM-DD
                    "amount": -50000,
                    "account_id": "abc",
                }
            ]
        )
        result = json.loads(validate_transactions(txn))
        assert any("YYYY-MM-DD" in w for w in result["warnings"])

    def test_warns_on_unusual_year(self):
        txn = json.dumps(
            [
                {
                    "date": "2015-05-15",
                    "amount": -50000,
                    "account_id": "abc",
                }
            ]
        )
        result = json.loads(validate_transactions(txn))
        assert any("unusual year" in w for w in result["warnings"])
