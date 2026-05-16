"""Tests for the YNAB API client (mocked)."""

from unittest.mock import AsyncMock, patch

import pytest

from src.services.ynab_client import YNABClient


@pytest.fixture
def client():
    """A YNABClient with a fake token for testing."""
    return YNABClient(base_url="https://api.ynab.com/v1", pat="fake-test-token")


class TestYNABClientAuth:
    """Tests for authentication behavior."""

    def test_raises_without_token(self):
        client = YNABClient(pat="")
        with pytest.raises(ValueError, match="Personal Access Token"):
            client._ensure_configured()

    def test_headers_include_bearer_token(self, client):
        headers = client._headers()
        assert headers["Authorization"] == "Bearer fake-test-token"
        assert headers["Content-Type"] == "application/json"


class TestYNABClientBudgets:
    """Tests for budget operations (mocked HTTP)."""

    async def test_list_budgets(self, client):
        mock_response = {
            "data": {
                "budgets": [
                    {"id": "budget-1", "name": "Mi Presupuesto", "last_modified_on": "2026-05-15"},
                    {"id": "budget-2", "name": "Negocio", "last_modified_on": "2026-05-10"},
                ]
            }
        }
        with patch.object(client, "_request", new_callable=AsyncMock, return_value=mock_response):
            budgets = await client.list_budgets()
            assert len(budgets) == 2
            assert budgets[0]["name"] == "Mi Presupuesto"

    async def test_list_accounts(self, client):
        mock_response = {
            "data": {
                "accounts": [
                    {
                        "id": "acc-1",
                        "name": "Davivienda TC",
                        "type": "creditCard",
                        "deleted": False,
                    },
                    {
                        "id": "acc-2",
                        "name": "Bancolombia Ahorros",
                        "type": "checking",
                        "deleted": False,
                    },
                ]
            }
        }
        with patch.object(client, "_request", new_callable=AsyncMock, return_value=mock_response):
            accounts = await client.list_accounts("budget-1")
            assert len(accounts) == 2
            assert accounts[1]["name"] == "Bancolombia Ahorros"


class TestYNABClientCategories:
    """Tests for category operations (mocked HTTP)."""

    async def test_list_categories(self, client):
        mock_response = {
            "data": {
                "category_groups": [
                    {
                        "id": "group-1",
                        "name": "Gastos Fijos",
                        "deleted": False,
                        "hidden": False,
                        "categories": [
                            {"id": "cat-1", "name": "Arriendo", "deleted": False, "hidden": False},
                            {"id": "cat-2", "name": "Servicios", "deleted": False, "hidden": False},
                        ],
                    }
                ]
            }
        }
        with patch.object(client, "_request", new_callable=AsyncMock, return_value=mock_response):
            groups = await client.list_categories("budget-1")
            assert len(groups) == 1
            assert len(groups[0]["categories"]) == 2


class TestYNABClientTransactions:
    """Tests for transaction creation (mocked HTTP)."""

    async def test_create_transactions(self, client):
        mock_response = {
            "data": {
                "transaction_ids": ["txn-1", "txn-2"],
                "duplicate_import_ids": [],
            }
        }
        transactions = [
            {"account_id": "acc-1", "date": "2026-05-15", "amount": -150500},
            {"account_id": "acc-1", "date": "2026-05-14", "amount": 3500000},
        ]
        with patch.object(client, "_request", new_callable=AsyncMock, return_value=mock_response):
            result = await client.create_transactions("budget-1", transactions)
            assert len(result["transaction_ids"]) == 2
            assert result["duplicate_import_ids"] == []
