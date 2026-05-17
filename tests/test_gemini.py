"""Tests for the Gemini host provider."""

import json
from unittest.mock import MagicMock, patch

import pytest
from google.genai import types

from src.hosts.gemini import GeminiProvider


@pytest.fixture
def gemini_provider():
    with patch("os.environ.get", return_value="fake_api_key"):
        with patch("google.genai.Client"):
            yield GeminiProvider()


def test_convert_tools(gemini_provider):
    """Test converting MCP tools to Gemini function declarations."""
    class FakeMCPTool:
        def __init__(self, name, description, input_schema):
            self.name = name
            self.description = description
            self.inputSchema = input_schema

    mcp_tools = [
        FakeMCPTool(
            name="test_tool",
            description="A test tool",
            input_schema={
                "type": "object",
                "properties": {
                    "param1": {"type": "string", "description": "A param"},
                },
                "required": ["param1"],
            },
        )
    ]

    tools = gemini_provider.convert_tools(mcp_tools)
    assert len(tools) == 1
    assert hasattr(tools[0], "function_declarations")
    assert len(tools[0].function_declarations) == 1
    decl = tools[0].function_declarations[0]
    assert decl.name == "test_tool"
    assert decl.description == "A test tool"
    if isinstance(decl.parameters, dict):
        assert decl.parameters["type"] == "OBJECT"
    else:
        assert decl.parameters.type == "OBJECT"


def test_get_assistant_message(gemini_provider):
    """Test get_assistant_message returns assistant role."""
    # Setup some fake parts
    gemini_provider._last_parts = ["fake_part"]
    msg = gemini_provider.get_assistant_message()
    assert msg["role"] == "assistant"
    assert msg["content"] == ["fake_part"]


def test_build_tool_results_message(gemini_provider):
    """Test building tool results message."""
    class FakeToolCall:
        def __init__(self, name):
            self.name = name

    results = [(FakeToolCall("test_tool"), "Success")]
    msg = gemini_provider.build_tool_results_message(results)
    
    assert msg["role"] == "user"
    assert len(msg["content"]) == 1
    assert msg["content"][0]["function_response"]["name"] == "test_tool"
    assert msg["content"][0]["function_response"]["response"]["result"] == "Success"


@pytest.mark.asyncio
async def test_send_message_system_instruction(gemini_provider):
    """Test that send_message handles system instructions and maps assistant to model."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
        {"role": "assistant", "content": "I am ready for the next request."},
        {
            "role": "user",
            "content": [
                {
                    "function_response": {
                        "name": "test_tool",
                        "response": {"result": "Success"},
                    }
                }
            ],
        },
    ]

    # Mock the client's generate_content call
    mock_response = MagicMock()
    mock_response.candidates = []
    gemini_provider._client.models.generate_content.return_value = mock_response

    response = await gemini_provider.send_message(messages, tools=[])
    
    # Check that generate_content was called
    gemini_provider._client.models.generate_content.assert_called_once()
    
    # Inspect the call arguments
    call_kwargs = gemini_provider._client.models.generate_content.call_args.kwargs
    assert call_kwargs["config"].system_instruction == "You are a helpful assistant."
    
    contents = call_kwargs["contents"]
    assert len(contents) == 3
    
    # 1. user
    assert contents[0].role == "user"
    assert len(contents[0].parts) == 1
    assert contents[0].parts[0].text == "Hello!"
    
    # 2. assistant -> model
    assert contents[1].role == "model"
    assert len(contents[1].parts) == 1
    assert contents[1].parts[0].text == "I am ready for the next request."
    
    # 3. user (function response)
    assert contents[2].role == "user"
    assert len(contents[2].parts) == 1
    assert hasattr(contents[2].parts[0], "function_response")
