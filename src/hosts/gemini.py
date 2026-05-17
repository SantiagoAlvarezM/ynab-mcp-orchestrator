"""Gemini (Google) LLM provider for the MCP host.

Uses the google-genai Python SDK to drive tool-use conversations.
Requires the GEMINI_API_KEY (or GOOGLE_API_KEY) environment variable.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

from google import genai
from google.genai import types
from mcp.types import Tool as MCPTool

from .base import BaseLLMProvider, LLMResponse, ToolCall


class GeminiProvider(BaseLLMProvider):
    """Google Gemini host provider."""

    DEFAULT_MODEL = "gemini-2.5-flash"

    def __init__(self, model: str | None = None) -> None:
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY (or GOOGLE_API_KEY) is not set. "
                "Get one at https://aistudio.google.com/apikey"
            )
        self._client = genai.Client(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL
        # Keep the full conversation as google-genai Content objects
        self._chat_history: list[types.Content] = []

    # ── interface ───────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return f"Gemini ({self._model})"

    def convert_tools(self, mcp_tools: list[MCPTool]) -> list[types.Tool]:
        """Convert MCP tools → Gemini function declarations."""
        declarations = []
        for tool in mcp_tools:
            schema = tool.inputSchema or {}
            # Build a clean parameter schema for Gemini
            properties = schema.get("properties", {})
            required = schema.get("required", [])

            # Clean up properties — remove unsupported fields
            clean_props: dict[str, Any] = {}
            for prop_name, prop_def in properties.items():
                clean_prop = _clean_schema_for_gemini(prop_def)
                clean_props[prop_name] = clean_prop

            parameters: dict[str, Any] | None = None
            if clean_props:
                parameters = {
                    "type": "OBJECT",
                    "properties": clean_props,
                }
                if required:
                    parameters["required"] = required

            declarations.append(
                types.FunctionDeclaration(
                    name=tool.name,
                    description=tool.description or "",
                    parameters=parameters,
                )
            )

        return [types.Tool(function_declarations=declarations)]

    async def send_message(
        self,
        messages: list[dict[str, Any]],
        tools: list[Any],
    ) -> LLMResponse:
        """Call the Gemini API."""
        # Extract system instruction
        system_instruction = None
        contents: list[types.Content] = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "system":
                system_instruction = content
                continue

            if role == "user":
                if isinstance(content, str):
                    contents.append(
                        types.Content(
                            role="user",
                            parts=[types.Part.from_text(text=content)],
                        )
                    )
                elif isinstance(content, list):
                    # Already structured parts (e.g. function responses)
                    parts = []
                    for item in content:
                        if isinstance(item, types.Part):
                            parts.append(item)
                        elif isinstance(item, dict) and "function_response" in item:
                            parts.append(
                                types.Part.from_function_response(
                                    name=item["function_response"]["name"],
                                    response=item["function_response"]["response"],
                                )
                            )
                    if parts:
                        contents.append(types.Content(role="user", parts=parts))

            elif role == "model" and isinstance(content, list):
                contents.append(types.Content(role="model", parts=content))

        config = types.GenerateContentConfig(
            tools=tools,
        )
        if system_instruction:
            config.system_instruction = system_instruction

        response = self._client.models.generate_content(
            model=self._model,
            contents=contents,
            config=config,
        )

        # Parse response
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        if response.candidates and response.candidates[0].content:
            self._last_parts = list(response.candidates[0].content.parts or [])
            for part in self._last_parts:
                if part.text:
                    text_parts.append(part.text)
                elif part.function_call:
                    fc = part.function_call
                    tool_calls.append(
                        ToolCall(
                            id=uuid.uuid4().hex,  # Unique ID to avoid identical IDs for parallel calls
                            name=fc.name,
                            arguments=dict(fc.args) if fc.args else {},
                        )
                    )
        else:
            self._last_parts = []

        finish_reason = ""
        if response.candidates:
            finish_reason = str(response.candidates[0].finish_reason or "")

        return LLMResponse(
            text="\n".join(text_parts),
            tool_calls=tool_calls,
            stop_reason=finish_reason,
        )

    def get_assistant_message(self) -> dict[str, Any]:
        """Return the raw message representing the model's response."""
        return {
            "role": "model",
            "content": self._last_parts,
        }

    def build_tool_results_message(
        self,
        results: list[tuple[ToolCall, str]],
    ) -> dict[str, Any]:
        """Build Gemini-format message to feed tool results back."""
        content = []
        for tc, result in results:
            content.append(
                {
                    "function_response": {
                        "name": tc.name,
                        "response": {"result": result},
                    }
                }
            )
        return {
            "role": "user",
            "content": content,
        }


def _clean_schema_for_gemini(schema: dict[str, Any]) -> dict[str, Any]:
    """Strip fields that Gemini's function calling doesn't support."""
    clean: dict[str, Any] = {}
    type_map = {
        "string": "STRING",
        "number": "NUMBER",
        "integer": "INTEGER",
        "boolean": "BOOLEAN",
        "array": "ARRAY",
        "object": "OBJECT",
    }
    if "type" in schema:
        clean["type"] = type_map.get(schema["type"], schema["type"])
    if "description" in schema:
        clean["description"] = schema["description"]
    if "enum" in schema:
        clean["enum"] = schema["enum"]
    if "items" in schema:
        clean["items"] = _clean_schema_for_gemini(schema["items"])
    if "properties" in schema:
        clean["properties"] = {
            k: _clean_schema_for_gemini(v) for k, v in schema["properties"].items()
        }
    if "required" in schema:
        clean["required"] = schema["required"]
    # Set default for optional string fields
    if clean.get("type") == "STRING" and "default" in schema:
        clean["description"] = (
            clean.get("description", "") + f" (default: {schema['default']})"
        ).strip()
    return clean
