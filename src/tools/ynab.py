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

    return [{"id": p["id"], "name": p["name"]} for p in payees if not p.get("deleted", False)]


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


def _transaction_summary(t: dict[str, Any]) -> dict[str, Any]:
    """Return the transaction fields useful for cleanup workflows."""
    return {
        "id": t.get("id"),
        "date": t.get("date"),
        "amount": t.get("amount"),
        "account_id": t.get("account_id"),
        "account_name": t.get("account_name"),
        "payee_id": t.get("payee_id"),
        "payee_name": t.get("payee_name"),
        "category_id": t.get("category_id"),
        "category_name": t.get("category_name"),
        "memo": t.get("memo"),
        "cleared": t.get("cleared"),
        "approved": t.get("approved"),
        "transfer_account_id": t.get("transfer_account_id"),
        "transfer_transaction_id": t.get("transfer_transaction_id"),
        "import_payee_name": t.get("import_payee_name"),
        "import_payee_name_original": t.get("import_payee_name_original"),
        "deleted": t.get("deleted", False),
    }


async def list_ynab_transactions(
    budget_id: str,
    since_date: str | None = None,
    account_id: str | None = None,
    include_deleted: bool = False,
) -> list[dict[str, Any]]:
    """List existing YNAB transactions for review and cleanup workflows."""
    try:
        transactions = await ynab_client.list_transactions(budget_id, since_date, account_id)
    except Exception as e:
        raise _wrap_error("list_ynab_transactions", e) from e

    return [
        _transaction_summary(t)
        for t in transactions
        if include_deleted or not t.get("deleted", False)
    ]


async def update_ynab_transactions(
    budget_id: str,
    updates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Update existing YNAB transactions by ID."""
    if not updates:
        raise ToolError("Transaction update list is empty.")

    missing_id = [i + 1 for i, update in enumerate(updates) if not update.get("id")]
    if missing_id:
        raise ToolError(f"Updates at positions {missing_id} are missing transaction id.")

    allowed_fields = {"id", "payee_id", "payee_name", "category_id", "memo", "approved", "cleared"}
    unsupported: dict[int, list[str]] = {}
    for i, update in enumerate(updates, start=1):
        extra = sorted(set(update) - allowed_fields)
        if extra:
            unsupported[i] = extra
    if unsupported:
        raise ToolError(f"Unsupported update fields: {unsupported}")

    try:
        result = await ynab_client.update_transactions(budget_id, updates)
    except Exception as e:
        raise _wrap_error("update_ynab_transactions", e) from e

    return {
        "updated_count": result.get("updated_count", 0),
        "failed_count": result.get("failed_count", 0),
        "transactions": [_transaction_summary(t) for t in result.get("transactions", [])],
        "failures": result.get("failures", []),
    }


def _brief_transfer_transaction(t: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": t.get("id"),
        "date": t.get("date"),
        "account_id": t.get("account_id"),
        "account_name": t.get("account_name"),
        "amount": t.get("amount"),
        "payee_name": t.get("payee_name"),
        "category_name": t.get("category_name"),
        "memo": t.get("memo"),
        "transfer_account_id": t.get("transfer_account_id"),
        "transfer_transaction_id": t.get("transfer_transaction_id"),
    }


async def find_internal_transfer_candidates(
    budget_id: str,
    since_date: str | None = None,
    account_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Find same-date, opposite-sign, same-amount transfer candidates."""
    try:
        transactions = await ynab_client.list_transactions(budget_id, since_date)
    except Exception as e:
        raise _wrap_error("find_internal_transfer_candidates", e) from e

    selected_accounts = set(account_ids or [])
    filtered = []
    for t in transactions:
        if t.get("deleted", False) or not t.get("amount"):
            continue
        if selected_accounts and t.get("account_id") not in selected_accounts:
            continue
        filtered.append(t)

    groups: dict[tuple[str, int], dict[str, list[dict[str, Any]]]] = {}
    for t in filtered:
        key = (t["date"], abs(t["amount"]))
        groups.setdefault(key, {"outflows": [], "inflows": []})
        groups[key]["outflows" if t["amount"] < 0 else "inflows"].append(t)

    exact_pairs = []
    ambiguous_groups = []
    already_linked_count = 0
    for (date, amount), group in sorted(groups.items()):
        pairs = [
            (outflow, inflow)
            for outflow in group["outflows"]
            for inflow in group["inflows"]
            if outflow.get("account_id") != inflow.get("account_id")
        ]
        if not pairs:
            continue
        linked_pairs = [
            (outflow, inflow)
            for outflow, inflow in pairs
            if outflow.get("transfer_transaction_id") == inflow.get("id")
            and inflow.get("transfer_transaction_id") == outflow.get("id")
        ]
        already_linked_count += len(linked_pairs)
        unlinked_pairs = [
            (outflow, inflow) for outflow, inflow in pairs if (outflow, inflow) not in linked_pairs
        ]
        if len(unlinked_pairs) == 1:
            outflow, inflow = unlinked_pairs[0]
            exact_pairs.append(
                {
                    "date": date,
                    "amount": amount,
                    "outflow": _brief_transfer_transaction(outflow),
                    "inflow": _brief_transfer_transaction(inflow),
                }
            )
        elif len(unlinked_pairs) > 1:
            ambiguous_groups.append(
                {
                    "date": date,
                    "amount": amount,
                    "pair_count": len(unlinked_pairs),
                    "outflows": [_brief_transfer_transaction(t) for t in group["outflows"]],
                    "inflows": [_brief_transfer_transaction(t) for t in group["inflows"]],
                }
            )

    return {
        "since_date": since_date,
        "account_ids": account_ids or [],
        "already_linked_pair_count": already_linked_count,
        "unlinked_exact_pair_count": len(exact_pairs),
        "ambiguous_group_count": len(ambiguous_groups),
        "unlinked_exact_pairs": exact_pairs,
        "ambiguous_groups": ambiguous_groups,
    }


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


async def delete_ynab_transactions(budget_id: str, transaction_ids: list[str]) -> dict[str, Any]:
    """Delete (rollback) transactions in YNAB."""
    if not transaction_ids:
        raise ToolError("Transaction ID list is empty.")

    try:
        return await ynab_client.delete_transactions(budget_id, transaction_ids)
    except Exception as e:
        raise _wrap_error("delete_ynab_transactions", e) from e
