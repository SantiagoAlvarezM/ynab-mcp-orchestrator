"""YNAB API tools — interact with budgets, accounts, categories, and transactions."""

from __future__ import annotations

import json

from pydantic import Field

from src.services.ynab_client import ynab_client


async def list_ynab_budgets() -> str:
    """List all YNAB budgets accessible with the configured Personal Access Token."""
    try:
        budgets = await ynab_client.list_budgets()
        summary = [
            {
                "id": b["id"],
                "name": b["name"],
                "last_modified_on": b.get("last_modified_on"),
            }
            for b in budgets
        ]
        return json.dumps(summary, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def list_ynab_accounts(
    budget_id: str = Field(description="YNAB budget UUID"),
) -> str:
    """List all accounts in a YNAB budget."""
    try:
        accounts = await ynab_client.list_accounts(budget_id)
        summary = [
            {
                "id": a["id"],
                "name": a["name"],
                "type": a["type"],
                "on_budget": a.get("on_budget"),
                "closed": a.get("closed"),
                "balance": a.get("balance"),
            }
            for a in accounts
            if not a.get("deleted", False)
        ]
        return json.dumps(summary, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def list_ynab_categories(
    budget_id: str = Field(description="YNAB budget UUID"),
) -> str:
    """List all category groups and their categories in a YNAB budget."""
    try:
        groups = await ynab_client.list_categories(budget_id)
        summary = []
        for group in groups:
            if group.get("deleted", False) or group.get("hidden", False):
                continue
            categories = [
                {
                    "id": c["id"],
                    "name": c["name"],
                    "budgeted": c.get("budgeted"),
                    "activity": c.get("activity"),
                    "balance": c.get("balance"),
                }
                for c in group.get("categories", [])
                if not c.get("deleted", False) and not c.get("hidden", False)
            ]
            if categories:
                summary.append(
                    {
                        "group_name": group["name"],
                        "group_id": group["id"],
                        "categories": categories,
                    }
                )
        return json.dumps(summary, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def get_ynab_payees(
    budget_id: str = Field(description="YNAB budget UUID"),
) -> str:
    """List all payees in a YNAB budget."""
    try:
        payees = await ynab_client.list_payees(budget_id)
        summary = [
            {"id": p["id"], "name": p["name"]} for p in payees if not p.get("deleted", False)
        ]
        return json.dumps(summary, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def create_ynab_account(
    budget_id: str = Field(description="YNAB budget UUID"),
    name: str = Field(description="Name of the new account"),
    type: str = Field(description="Type of account (e.g. 'checking', 'savings', 'creditCard')"),
    balance: int = Field(default=0, description="Initial balance in milliunits"),
) -> str:
    """Create a new account in a YNAB budget."""
    try:
        account = await ynab_client.create_account(budget_id, name, type, balance)
        return json.dumps(account, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def create_ynab_category(
    budget_id: str = Field(description="YNAB budget UUID"),
    name: str = Field(description="Name of the new category"),
    category_group_id: str = Field(description="UUID of the category group to place this in"),
) -> str:
    """Create a new category in a YNAB budget."""
    try:
        category = await ynab_client.create_category(budget_id, name, category_group_id)
        return json.dumps(category, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def create_ynab_payee(
    budget_id: str = Field(description="YNAB budget UUID"),
    name: str = Field(description="Name of the new payee"),
) -> str:
    """Create a new payee in a YNAB budget."""
    try:
        payee = await ynab_client.create_payee(budget_id, name)
        return json.dumps(payee, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def create_ynab_transactions(
    budget_id: str = Field(description="YNAB budget UUID"),
    transactions_json: str = Field(
        description="JSON array of transaction objects to create.",
    ),
) -> str:
    """Create transactions in YNAB."""
    try:
        transactions = json.loads(transactions_json)

        if not isinstance(transactions, list):
            return json.dumps({"error": "Expected a JSON array of transaction objects."})

        if not transactions:
            return json.dumps({"error": "Transaction list is empty."})

        missing_account = [i + 1 for i, t in enumerate(transactions) if not t.get("account_id")]
        if missing_account:
            return json.dumps(
                {
                    "error": (
                        f"Transactions at positions {missing_account} are missing "
                        "account_id. All transactions must have an account_id."
                    ),
                }
            )

        result = await ynab_client.create_transactions(budget_id, transactions)

        return json.dumps(
            {
                "success": True,
                "created_count": len(result.get("transaction_ids", [])),
                "transaction_ids": result.get("transaction_ids", []),
                "duplicate_import_ids": result.get("duplicate_import_ids", []),
            },
            indent=2,
        )

    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {e}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def delete_ynab_transactions(
    budget_id: str = Field(description="YNAB budget UUID"),
    transaction_ids_json: str = Field(
        description='JSON array of strings representing the transaction UUIDs to delete. e.g. ["uuid1", "uuid2"]',
    ),
) -> str:
    """Delete (rollback) transactions in YNAB."""
    try:
        transaction_ids = json.loads(transaction_ids_json)

        if not isinstance(transaction_ids, list):
            return json.dumps({"error": "Expected a JSON array of transaction IDs."})

        if not transaction_ids:
            return json.dumps({"error": "Transaction ID list is empty."})

        result = await ynab_client.delete_transactions(budget_id, transaction_ids)
        return json.dumps(result, indent=2, ensure_ascii=False)

    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {e}"})
    except Exception as e:
        return json.dumps({"error": str(e)})
