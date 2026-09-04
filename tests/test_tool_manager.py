"""
Tests for ToolManager's routing, clarification, and error-handling
behavior. Uses small fake tools instead of real ones so these tests
stay fast and don't touch the OS/network/subprocess at all.
"""

import pytest

from tools.registry import ToolRegistry
from tools.manager import ToolManager
from tools.base_tool import BaseTool
from tools.tool_result import ToolResult


class FakeTool(BaseTool):
    """A minimal configurable tool for testing ToolManager in isolation."""

    def __init__(
        self,
        tool_name="fake",
        handles=lambda q: False,
        result=None,
        raises=None,
        pending=False,
    ):
        self._name = tool_name
        self._handles = handles
        self._result = result
        self._raises = raises
        self._pending = pending

    @property
    def name(self):
        return self._name

    @property
    def description(self):
        return "A fake tool for tests."

    def can_handle(self, query):
        return self._handles(query)

    def execute(self, query):
        if self._raises:
            raise self._raises
        return self._result

    def has_pending_clarification(self):
        return self._pending

    def resolve_clarification(self, user_input):
        if self._raises:
            raise self._raises
        return self._result


@pytest.fixture
def manager_with(request):
    """Build a ToolManager wired with the given list of tools."""

    def _build(tools):
        registry = ToolRegistry()
        for tool in tools:
            registry.register(tool)
        return ToolManager(registry)

    return _build


def test_dispatches_to_first_matching_tool(manager_with):
    matched_result = ToolResult(success=True, tool_name="b", data="from b")

    tool_a = FakeTool("a", handles=lambda q: False)
    tool_b = FakeTool("b", handles=lambda q: True, result=matched_result)

    manager = manager_with([tool_a, tool_b])
    result = manager.execute("anything")

    assert result is matched_result


def test_no_tool_matched_returns_tool_manager_sentinel(manager_with):
    tool_a = FakeTool("a", handles=lambda q: False)

    manager = manager_with([tool_a])
    result = manager.execute("hi")

    assert result.success is False
    assert result.tool_name == "ToolManager"
    assert result.error == "No suitable tool found."


def test_exception_in_execute_is_caught_and_reported(manager_with):
    tool_a = FakeTool(
        "a", handles=lambda q: True, raises=ValueError("boom")
    )

    manager = manager_with([tool_a])
    result = manager.execute("anything")

    assert result.success is False
    assert result.tool_name == "a"
    assert "boom" in result.error


def test_pending_clarification_is_checked_before_normal_routing(manager_with):
    clarified_result = ToolResult(
        success=True, tool_name="a", data="resolved"
    )

    # This tool has a pending clarification AND would not normally
    # match this query via can_handle -- resolve_clarification should
    # still be called first.
    tool_a = FakeTool(
        "a",
        handles=lambda q: False,
        pending=True,
        result=clarified_result,
    )

    manager = manager_with([tool_a])
    result = manager.execute("1")

    assert result is clarified_result


def test_exception_in_resolve_clarification_is_caught(manager_with):
    tool_a = FakeTool(
        "a", pending=True, raises=RuntimeError("clarify boom")
    )

    manager = manager_with([tool_a])
    result = manager.execute("2")

    assert result.success is False
    assert result.tool_name == "a"
    assert "clarify boom" in result.error