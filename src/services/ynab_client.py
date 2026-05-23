"""YNAB REST API client.

Wraps the YNAB v1 API using httpx for async HTTP.
Reference: https://api.ynab.com/v1
"""

from __future__ import annotations

import asyncio
import urllib.parse
from typing import Any

import httpx

from src.config import YNAB_BASE_URL, YNAB_PAT


class YNABClient:
    """Async client for the YNAB REST API.

    Holds a single long-lived httpx.AsyncClient so connections are pooled
    across calls. Callers should invoke `aclose()` at shutdown — the
    FastMCP lifespan in server.py wires this up.
    """

    def __init__(
        self,
        base_url: str = YNAB_BASE_URL,
        pat: str = YNAB_PAT,
    ):
        self._base_url = base_url.rstrip("/")
        self._pat = pat
        self._http: httpx.AsyncClient | None = None

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._pat}",
            "Content-Type": "application/json",
        }

    def _ensure_configured(self) -> None:
        if not self._pat:
            raise ValueError(
                "YNAB Personal Access Token not configured. Set YNAB_PAT in your .env file."
            )

    def _get_http(self) -> httpx.AsyncClient:
        """Return the shared httpx client, lazily creating it on first use."""
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                base_url=self._base_url,
                headers=self._headers(),
                timeout=30.0,
            )
        return self._http

    async def aclose(self) -> None:
        """Close the underlying HTTP connection pool. Idempotent."""
        if self._http is not None and not self._http.is_closed:
            await self._http.aclose()
        self._http = None

    async def _request(
        self,
        method: str,
        path: str,
        json_body: dict | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated request to the YNAB API."""
        self._ensure_configured()
        http = self._get_http()

        response = await http.request(method=method, url=path, json=json_body)

        if response.status_code >= 400:
            error_detail = response.text
            try:
                error_json = response.json()
                error_detail = error_json.get("error", {}).get("detail", response.text)
            except Exception:
                pass  # nosec B110

            raise httpx.HTTPStatusError(
                f"YNAB API error ({response.status_code}): {error_detail}",
                request=response.request,
                response=response,
            )

        return response.json()

    # ── Budgets ─────────────────────────────────────────────────────────────

    async def list_budgets(self) -> list[dict]:
        """List all budgets."""
        data = await self._request("GET", "/budgets")
        return data.get("data", {}).get("budgets", [])

    async def get_budget(self, budget_id: str) -> dict:
        """Get a specific budget."""
        budget_id = urllib.parse.quote(budget_id, safe="")
        data = await self._request("GET", f"/budgets/{budget_id}")
        return data.get("data", {}).get("budget", {})

    # ── Accounts ────────────────────────────────────────────────────────────

    async def list_accounts(self, budget_id: str) -> list[dict]:
        """List all accounts in a budget."""
        budget_id = urllib.parse.quote(budget_id, safe="")
        data = await self._request("GET", f"/budgets/{budget_id}/accounts")
        return data.get("data", {}).get("accounts", [])

    async def create_account(
        self, budget_id: str, name: str, account_type: str, balance: int = 0
    ) -> dict:
        """Create a new account in a budget."""
        budget_id = urllib.parse.quote(budget_id, safe="")
        body = {"account": {"name": name, "type": account_type, "balance": balance}}
        data = await self._request("POST", f"/budgets/{budget_id}/accounts", json_body=body)
        return data.get("data", {}).get("account", {})

    # ── Categories ──────────────────────────────────────────────────────────

    async def list_categories(self, budget_id: str) -> list[dict]:
        """List all category groups and their categories in a budget."""
        budget_id = urllib.parse.quote(budget_id, safe="")
        data = await self._request("GET", f"/budgets/{budget_id}/categories")
        return data.get("data", {}).get("category_groups", [])

    async def create_category(self, budget_id: str, name: str, category_group_id: str) -> dict:
        """Create a new category in a budget."""
        budget_id = urllib.parse.quote(budget_id, safe="")
        body = {"category": {"name": name, "category_group_id": category_group_id}}
        data = await self._request("POST", f"/budgets/{budget_id}/categories", json_body=body)
        return data.get("data", {}).get("category", {})

    # ── Payees ──────────────────────────────────────────────────────────────

    async def list_payees(self, budget_id: str) -> list[dict]:
        """List all payees in a budget."""
        budget_id = urllib.parse.quote(budget_id, safe="")
        data = await self._request("GET", f"/budgets/{budget_id}/payees")
        return data.get("data", {}).get("payees", [])

    async def create_payee(self, budget_id: str, name: str) -> dict:
        """Create a new payee in a budget."""
        budget_id = urllib.parse.quote(budget_id, safe="")
        body = {"payee": {"name": name}}
        data = await self._request("POST", f"/budgets/{budget_id}/payees", json_body=body)
        return data.get("data", {}).get("payee", {})

    # ── Transactions ────────────────────────────────────────────────────────

    async def create_transactions(
        self,
        budget_id: str,
        transactions: list[dict],
    ) -> dict:
        """Create one or more transactions in a budget.

        Args:
            budget_id: The YNAB budget UUID.
            transactions: List of transaction dicts conforming to YNAB's API spec.
                Each must have: account_id, date, amount.
                Optional: payee_name, memo, cleared, approved, category_id.

        Returns:
            Dict with 'transaction_ids', 'duplicate_import_ids', etc.
        """
        budget_id = urllib.parse.quote(budget_id, safe="")
        body = {"transactions": transactions}
        data = await self._request("POST", f"/budgets/{budget_id}/transactions", json_body=body)
        return data.get("data", {})

    async def delete_transactions(
        self,
        budget_id: str,
        transaction_ids: list[str],
    ) -> dict:
        """Delete one or more transactions in a budget.

        Args:
            budget_id: The YNAB budget UUID.
            transaction_ids: List of transaction UUIDs to delete.

        Returns:
            Dict showing success count and failures.
        """
        budget_id = urllib.parse.quote(budget_id, safe="")

        # YNAB's API has no bulk-delete endpoint, but the per-id calls are
        # independent — fan them out concurrently so a 200-row rollback is
        # bounded by latency, not N x latency.
        async def _delete_one(tid: str) -> tuple[str, Exception | None]:
            try:
                await self._request(
                    "DELETE",
                    f"/budgets/{budget_id}/transactions/{urllib.parse.quote(tid, safe='')}",
                )
                return tid, None
            except Exception as e:
                return tid, e

        results = await asyncio.gather(*(_delete_one(tid) for tid in transaction_ids))

        success_count = 0
        failures: list[dict[str, str]] = []
        for tid, err in results:
            if err is None:
                success_count += 1
            else:
                failures.append({"id": tid, "error": str(err)})

        return {"success_count": success_count, "failed_count": len(failures), "failures": failures}


ynab_client = YNABClient()
