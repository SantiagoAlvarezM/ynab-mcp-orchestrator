"""Tests for the transaction validation tool."""

import json

from src.tools.validation import validate_transactions


class TestValidTransactions:
    """Tests for validating correct transactions."""

    def test_valid_transactions_pass(self, valid_transactions):
        result = json.loads(validate_transactions(valid_transactions))
        assert result["is_valid"] is True
        assert result["total_transactions"] == 2
        assert result["valid_count"] == 2
        assert result["error_count"] == 0

    def test_single_valid_transaction(self):
        result = json.loads(
            validate_transactions(
                [
                    {
                        "date": "2026-05-15",
                        "amount": -50000,
                        "payee_name": "Test",
                        "account_id": "abc-123",
                    }
                ]
            )
        )
        assert result["is_valid"] is True
        assert result["valid_count"] == 1


class TestInvalidTransactions:
    """Tests for detecting invalid transactions."""

    def test_missing_required_fields(self, invalid_transactions):
        result = json.loads(validate_transactions(invalid_transactions))
        assert result["is_valid"] is False
        assert result["error_count"] > 0
        assert len(result["errors"]) > 0

    def test_empty_list(self):
        result = json.loads(validate_transactions([]))
        assert result["is_valid"] is True
        assert result["total_transactions"] == 0


class TestSemanticWarnings:
    """Tests for semantic validation warnings."""

    def test_warns_on_missing_payee(self):
        result = json.loads(
            validate_transactions(
                [{"date": "2026-05-15", "amount": -50000, "account_id": "abc"}]
            )
        )
        assert result["is_valid"] is True
        assert any("payee_name" in w for w in result["warnings"])

    def test_warns_on_missing_account_id(self):
        result = json.loads(
            validate_transactions(
                [{"date": "2026-05-15", "amount": -50000, "payee_name": "Test"}]
            )
        )
        assert any("account_id" in w for w in result["warnings"])

    def test_warns_on_zero_amount(self):
        result = json.loads(
            validate_transactions(
                [
                    {
                        "date": "2026-05-15",
                        "amount": 0,
                        "payee_name": "Test",
                        "account_id": "abc",
                    }
                ]
            )
        )
        assert any("zero" in w for w in result["warnings"])

    def test_warns_on_bad_date_format(self):
        result = json.loads(
            validate_transactions(
                [
                    {
                        "date": "15/05/2026",  # DD/MM/YYYY instead of YYYY-MM-DD
                        "amount": -50000,
                        "account_id": "abc",
                    }
                ]
            )
        )
        assert any("YYYY-MM-DD" in w for w in result["warnings"])

    def test_warns_on_unusual_year(self):
        result = json.loads(
            validate_transactions(
                [{"date": "2015-05-15", "amount": -50000, "account_id": "abc"}]
            )
        )
        assert any("unusual year" in w for w in result["warnings"])
