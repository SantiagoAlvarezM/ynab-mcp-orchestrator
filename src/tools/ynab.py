"""YNAB API tools — interact with budgets, accounts, categories, and transactions."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp.exceptions import ToolError

from src.services.ynab_client import ynab_client


def _wrap_error(operation: str, exc: Exception) -> ToolError:
    """Convert an upstream exception into a ToolError with operation context."""
    return ToolError(f"{operation} failed: {exc}")


async def list_ynab_budgets() -> list[dict[str, Any]]:
    """List all YNAB budgets accessible with the configured Personal Access Token."""
    try:
        budgets = await ynab_client.list_budgets()
    except Exception as e:
        raise _wrap_error("list_ynab_budgets", e) from e

    return [
        {
            "id": b["id"],
            "name": b["name"],
            "last_modified_on": b.get("last_modified_on"),
        }
        for b in budgets
    ]


async def list_ynab_accounts(budget_id: str) -> list[dict[str, Any]]:
    """List all accounts in a YNAB budget."""
    try:
        accounts = await ynab_client.list_accounts(budget_id)
    except Exception as e:
        raise _wrap_error("list_ynab_accounts", e) from e

    return [
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


async def list_ynab_categories(budget_id: str) -> list[dict[str, Any]]:
    """List all category groups and their categories in a YNAB budget."""
    try:
        groups = await ynab_client.list_categories(budget_id)
    except Exception as e:
        raise _wrap_error("list_ynab_categories", e) from e

    summary: list[dict[str, Any]] = []
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
    return summary


async def list_ynab_payees(budget_id: str) -> list[dict[str, Any]]:
    """List all payees in a YNAB budget."""
    try:
        payees = await ynab_client.list_payees(budget_id)
    except Exception as e:
        raise _wrap_error("list_ynab_payees", e) from e

    return [
        {"id": p["id"], "name": p["name"]} for p in payees if not p.get("deleted", False)
    ]


async def create_ynab_account(
    budget_id: str,
    name: str,
    account_type: str,
    balance: int = 0,
) -> dict[str, Any]:
    """Create a new account in a YNAB budget."""
    try:
        return await ynab_client.create_account(budget_id, name, account_type, balance)
    except Exception as e:
        raise _wrap_error("create_ynab_account", e) from e


async def create_ynab_category(
    budget_id: str,
    name: str,
    category_group_id: str,
) -> dict[str, Any]:
    """Create a new category in a YNAB budget."""
    try:
        return await ynab_client.create_category(budget_id, name, category_group_id)
    except Exception as e:
        raise _wrap_error("create_ynab_category", e) from e


async def create_ynab_payee(budget_id: str, name: str) -> dict[str, Any]:
    """Create a new payee in a YNAB budget."""
    try:
        return await ynab_client.create_payee(budget_id, name)
    except Exception as e:
        raise _wrap_error("create_ynab_payee", e) from e


async def create_ynab_transactions(
    budget_id: str, transactions: list[dict[str, Any]]
) -> dict[str, Any]:
    """Create transactions in YNAB."""
    if not transactions:
        raise ToolError("Transaction list is empty.")

    missing_account = [i + 1 for i, t in enumerate(transactions) if not t.get("account_id")]
    if missing_account:
        raise ToolError(
            f"Transactions at positions {missing_account} are missing account_id. "
            "All transactions must have an account_id before being pushed to YNAB."
        )

    try:
        result = await ynab_client.create_transactions(budget_id, transactions)
    except Exception as e:
        raise _wrap_error("create_ynab_transactions", e) from e

    return {
        "success": True,
        "created_count": len(result.get("transaction_ids", [])),
        "transaction_ids": result.get("transaction_ids", []),
        "duplicate_import_ids": result.get("duplicate_import_ids", []),
    }


async def delete_ynab_transactions(
    budget_id: str, transaction_ids: list[str]
) -> dict[str, Any]:
    """Delete (rollback) transactions in YNAB."""
    if not transaction_ids:
        raise ToolError("Transaction ID list is empty.")

    try:
        return await ynab_client.delete_transactions(budget_id, transaction_ids)
    except Exception as e:
        raise _wrap_error("delete_ynab_transactions", e) from e
