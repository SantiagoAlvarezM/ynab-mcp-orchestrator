"""Claude (Anthropic) LLM provider for the MCP host.

Uses the Anthropic Python SDK to drive tool-use conversations.
Requires the ANTHROPIC_API_KEY environment variable.
"""

from __future__ import annotations

import os
from typing import Any

from anthropic import Anthropic
from mcp.types import Tool as MCPTool

from .base import BaseLLMProvider, LLMResponse, ToolCall


class ClaudeProvider(BaseLLMProvider):
    """Anthropic Claude host provider."""

    DEFAULT_MODEL = "claude-sonnet-4-20250514"

    def __init__(self, model: str | None = None, max_tokens: int = 8_192) -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. "
                "Get one at https://console.anthropic.com/settings/keys"
            )
        self._client = Anthropic(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL
        self._max_tokens = max_tokens
        # Store the raw Anthropic response so build_tool_result_messages
        # can reference the full content block list.
        self._last_raw_content: list[Any] = []

    # ── interface ───────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return f"Claude ({self._model})"

    def convert_tools(self, mcp_tools: list[MCPTool]) -> list[dict[str, Any]]:
        """Convert MCP tools → Anthropic tool format."""
        return [
            {
                "name": tool.name,
                "description": tool.description or "",
                "input_schema": tool.inputSchema,
            }
            for tool in mcp_tools
        ]

    async def send_message(
        self,
        messages: list[dict[str, Any]],
        tools: list[Any],
    ) -> LLMResponse:
        """Call the Anthropic Messages API."""
        # Separate system prompt from messages
        system_prompt = None
        api_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                api_messages.append(msg)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": api_messages,
            "tools": tools,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        response = self._client.messages.create(**kwargs)

        # Parse response
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        self._last_raw_content = list(response.content)

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=block.input if isinstance(block.input, dict) else {},
                    )
                )

        return LLMResponse(
            text="\n".join(text_parts),
            tool_calls=tool_calls,
            stop_reason=response.stop_reason or "",
        )

    def get_assistant_message(self) -> dict[str, Any]:
        """Return the raw message representing the model's response."""
        return {
            "role": "assistant",
            "content": self._last_raw_content,
        }

    def build_tool_results_message(
        self,
        results: list[tuple[ToolCall, str]],
    ) -> dict[str, Any]:
        """Build Anthropic-format message to feed tool results back."""
        content = []
        for tc, result in results:
            content.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": result,
                }
            )
        return {
            "role": "user",
            "content": content,
        }
