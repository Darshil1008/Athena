"""
Tests for Athena.process_request()'s routing logic: direct tool
success, search-result synthesis, no-tool-matched fallback,
real-tool-failure grounding, and clarification listing.

LLMClient is mocked throughout -- these tests never call Ollama.
"""

from unittest.mock import MagicMock, patch

import pytest

from core.assistant import Athena
from tools.tool_result import ToolResult


@pytest.fixture
def athena():
    fake_tool_manager = MagicMock()

    with patch("core.assistant.LLMClient"):
        instance = Athena(fake_tool_manager)

    instance.client = MagicMock()
    return instance


def test_successful_tool_result_returned_directly(athena):
    athena.tool_manager.execute.return_value = ToolResult(
        success=True, tool_name="calculator", data=4
    )

    result = athena.process_request("2+2", [])

    assert result == "4"
    athena.client.generate.assert_not_called()


def test_search_result_triggers_synthesis_not_raw_return(athena):
    athena.tool_manager.execute.return_value = ToolResult(
        success=True,
        tool_name="search",
        data="who is the pm",
        metadata={
            "needs_synthesis": True,
            "search_results": "1. Foo\nBar snippet",
        },
    )
    athena.client.generate.return_value = "Based on current results, ..."

    result = athena.process_request("search: who is the pm", [])

    assert result == "Based on current results, ..."
    athena.client.generate.assert_called_once()

    grounded_history = athena.client.generate.call_args[0][0]
    system_messages = [
        m["content"] for m in grounded_history if m["role"] == "system"
    ]
    assert any("search results" in c.lower() for c in system_messages)
    assert any("Bar snippet" in c for c in system_messages)


def test_no_tool_matched_falls_through_to_plain_generate(athena):
    athena.tool_manager.execute.return_value = ToolResult(
        success=False,
        tool_name="ToolManager",
        error="No suitable tool found.",
    )
    athena.client.generate.return_value = "Hey there!"

    original_history = [{"role": "user", "content": "Hi"}]
    result = athena.process_request("Hi", original_history)

    assert result == "Hey there!"
    # Must be ungrounded -- history passed through unchanged.
    athena.client.generate.assert_called_once_with(original_history)


def test_real_tool_failure_grounds_the_llm(athena):
    athena.tool_manager.execute.return_value = ToolResult(
        success=False, tool_name="os", error="App not found."
    )
    athena.client.generate.return_value = "Sorry, that didn't work."

    result = athena.process_request("open zzz", [])

    assert result == "Sorry, that didn't work."
    grounded_history = athena.client.generate.call_args[0][0]
    system_messages = [
        m["content"] for m in grounded_history if m["role"] == "system"
    ]
    assert any("failed" in c.lower() for c in system_messages)


def test_clarification_metadata_returns_deterministic_listing(athena):
    athena.tool_manager.execute.return_value = ToolResult(
        success=False,
        tool_name="os",
        metadata={
            "clarification": True,
            "options": ["VS Code", "VS Code Insiders"],
        },
    )

    result = athena.process_request("open code", [])

    assert "VS Code" in result
    assert "VS Code Insiders" in result
    athena.client.generate.assert_not_called()