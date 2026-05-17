"""YNAB MCP Orchestrator — Interactive Host (MCP Client).

Connects to the YNAB MCP Server and uses an LLM (Claude or Gemini) to
drive tool-use conversations interactively from the terminal.

Usage:
    # Claude (default)
    uv run host.py

    # Gemini
    uv run host.py --provider gemini

    # Specify a custom model
    uv run host.py --provider claude --model claude-sonnet-4-20250514
"""

from __future__ import annotations

import argparse
import asyncio
import os
from contextlib import AsyncExitStack
from typing import Any

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

load_dotenv()

# ── constants ──────────────────────────────────────────────────────────────

SERVER_SCRIPT = os.path.join(os.path.dirname(__file__), "server.py")

SYSTEM_PROMPT = """\
You are a financial assistant that helps the user manage their YNAB budget.
You have access to tools for reading bank statements, extracting transactions,
validating data, and syncing with YNAB.

Key rules:
- Always validate transactions before pushing to YNAB.
- Amounts are in Colombian Pesos (COP) unless stated otherwise.
- Convert amounts to YNAB milliunits (multiply by 1000).
- Dates from Colombian banks are DD/MM/YYYY — convert to YYYY-MM-DD.
- Be concise but thorough in your summaries.
- FORMATTING: Use rich Markdown formatting. Display tabular data (like extracted transactions) using Markdown tables. When displaying JSON, always use proper indentation and Markdown code blocks.
"""


# ── provider factory ───────────────────────────────────────────────────────


def create_provider(
    provider_name: str,
    model: str | None = None,
):
    """Create an LLM provider by name."""
    if provider_name == "claude":
        from src.hosts.claude import ClaudeProvider

        return ClaudeProvider(model=model)
    elif provider_name == "gemini":
        from src.hosts.gemini import GeminiProvider

        return GeminiProvider(model=model)
    else:
        raise ValueError(f"Unknown provider: {provider_name!r}. Use 'claude' or 'gemini'.")


# ── main ───────────────────────────────────────────────────────────────────


async def main(provider_name: str, model: str | None = None) -> None:
    provider = create_provider(provider_name, model)

    print(f"\n{'═' * 60}")
    print(f"  YNAB MCP Orchestrator — {provider.name}")
    print(f"{'═' * 60}")
    print("  Connecting to MCP server...")

    exit_stack = AsyncExitStack()

    try:
        # 1. Connect to the MCP server via stdio
        server_params = StdioServerParameters(
            command="uv",
            args=["run", SERVER_SCRIPT],
            env={
                **os.environ,
                # Ensure the server inherits our env (YNAB_PAT, etc.)
            },
        )

        stdio_transport = await exit_stack.enter_async_context(
            stdio_client(server_params),
        )
        read_stream, write_stream = stdio_transport

        session = await exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream),
        )
        await session.initialize()

        # 2. Discover tools
        tools_response = await session.list_tools()
        mcp_tools = tools_response.tools
        tool_names = [t.name for t in mcp_tools]
        print(f"  ✅ Connected! {len(mcp_tools)} tools available:")
        for name in tool_names:
            print(f"     • {name}")
        print(f"{'─' * 60}")
        print("  Type your query, or 'quit' / 'exit' to stop.\n")

        # 3. Interactive loop
        messages_history: list[dict[str, Any]] = []
        if SYSTEM_PROMPT:
            messages_history.append({"role": "system", "content": SYSTEM_PROMPT})

        while True:
            try:
                query = input("You ▸ ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\n👋 Goodbye!")
                break

            if not query:
                continue
            if query.lower() in {"quit", "exit", "q"}:
                print("\n👋 Goodbye!")
                break

            print(f"\n{provider.name} is thinking...\n")

            messages_history.append({"role": "user", "content": query})

            try:
                response = await provider.run_agentic_loop(
                    messages=messages_history,
                    session=session,
                    mcp_tools=mcp_tools,
                )
                console = Console()
                console.print(Panel(Markdown(response), title=f"🤖 {provider.name}", expand=False))
                print()
            except Exception as exc:
                print(f"\n❌ Error: {exc}\n")

    finally:
        await exit_stack.aclose()


def cli() -> None:
    parser = argparse.ArgumentParser(
        description="YNAB MCP Orchestrator — Interactive AI Host",
    )
    parser.add_argument(
        "-p",
        "--provider",
        choices=["claude", "gemini"],
        default="claude",
        help="LLM provider to use (default: claude)",
    )
    parser.add_argument(
        "-m",
        "--model",
        default=None,
        help="Override the default model for the chosen provider",
    )
    args = parser.parse_args()
    asyncio.run(main(args.provider, args.model))


if __name__ == "__main__":
    cli()
