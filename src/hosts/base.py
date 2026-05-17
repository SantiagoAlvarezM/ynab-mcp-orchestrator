"""Abstract base class for LLM host providers.

Each provider translates between MCP tool schemas and the LLM's native
function-calling format, then runs the agentic tool-use loop until the
model produces a final text response.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from mcp import ClientSession
from mcp.types import Tool as MCPTool


@dataclass
class ToolCall:
    """Represents a single tool invocation requested by the LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """Unified response from any LLM provider."""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = ""


class BaseLLMProvider(ABC):
    """Interface every LLM host must implement."""

    # ── abstract ────────────────────────────────────────────────────────

    @abstractmethod
    def convert_tools(self, mcp_tools: list[MCPTool]) -> list[Any]:
        """Convert MCP tool definitions to the provider's native format."""

    @abstractmethod
    async def send_message(
        self,
        messages: list[dict[str, Any]],
        tools: list[Any],
    ) -> LLMResponse:
        """Send messages + tool definitions and return the model response."""

    @abstractmethod
    def get_assistant_message(self) -> dict[str, Any]:
        """Return the raw message representing the model's response."""

    @abstractmethod
    def build_tool_results_message(
        self,
        results: list[tuple[ToolCall, str]],
    ) -> dict[str, Any]:
        """Build the user message containing all tool results."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name (e.g. 'Claude', 'Gemini')."""

    # ── shared agentic loop ─────────────────────────────────────────────

    async def run_agentic_loop(
        self,
        messages: list[dict[str, Any]],
        session: ClientSession,
        mcp_tools: list[MCPTool],
        *,
        max_iterations: int = 25,
    ) -> str:
        """Execute the full tool-use loop until the model stops calling tools.

        Mutates `messages` in-place by appending assistant responses and tool results.
        Returns the concatenated text output for this interaction.
        """
        native_tools = self.convert_tools(mcp_tools)
        output_parts: list[str] = []

        for _iteration in range(max_iterations):
            response = await self.send_message(messages, native_tools)

            if response.text:
                output_parts.append(response.text)

            messages.append(self.get_assistant_message())

            if not response.tool_calls:
                # Model is done — no more tool calls
                break

            tool_results = []
            for tc in response.tool_calls:
                print(f"  🔧 [{tc.name}] {json.dumps(tc.arguments, ensure_ascii=False)}")

                try:
                    result = await session.call_tool(tc.name, tc.arguments)
                    tool_output = _extract_tool_text(result)
                except Exception as exc:
                    tool_output = f"⚠️  Tool error: {exc}"

                tool_results.append((tc, tool_output))

            messages.append(self.build_tool_results_message(tool_results))

        else:
            output_parts.append(
                f"\n⚠️  Reached max iterations ({max_iterations}). The model may not have finished."
            )

        return "\n".join(output_parts)


def _extract_tool_text(result: Any) -> str:
    """Pull plain text from an MCP CallToolResult."""
    if hasattr(result, "content"):
        parts = []
        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        if parts:
            return "\n".join(parts)
    return str(result)
