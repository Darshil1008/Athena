"""
Tool manager for Athena.

Responsible for selecting and executing the appropriate tool.
"""

from core.logger import Logger

from .registry import ToolRegistry
from .tool_result import ToolResult


class ToolManager:
    """
    Coordinates tool selection and execution.
    """

    def __init__(self, registry: ToolRegistry):
        self._registry = registry

    def execute(self, query: str) -> ToolResult:
        """
        Resume any tool waiting on a clarifying answer first;
        otherwise find the first tool capable of handling the query
        and execute it.

        All logging for tool dispatch happens here, in one place,
        rather than duplicated inside every individual tool.
        """

        for tool in self._registry.list_tools():

            if tool.has_pending_clarification():

                Logger.info(
                    f"Resolving pending clarification via '{tool.name}'."
                )

                try:
                    result = tool.resolve_clarification(query)
                    self._log_result(result)
                    return result

                except Exception as e:
                    Logger.error(
                        f"Tool '{tool.name}' raised during "
                        f"resolve_clarification: {e}"
                    )
                    return ToolResult(
                        success=False,
                        tool_name=tool.name,
                        error=str(e)
                    )

        for tool in self._registry.list_tools():

            if tool.can_handle(query):

                Logger.info(f"Dispatching to '{tool.name}': {query!r}")

                try:
                    result = tool.execute(query)
                    self._log_result(result)
                    return result

                except Exception as e:
                    Logger.error(
                        f"Tool '{tool.name}' raised during execute: {e}"
                    )
                    return ToolResult(
                        success=False,
                        tool_name=tool.name,
                        error=str(e)
                    )

        Logger.info(f"No tool matched query: {query!r}")

        return ToolResult(
            success=False,
            tool_name="ToolManager",
            error="No suitable tool found."
        )

    def get_tool(self, name: str):
        """
        Return a registered tool by name, or None if not found.

        Used by Athena to reach a specific tool directly (e.g. the
        search tool, when the Planner determines current information
        is needed but no tool's trigger words matched).
        """
        return self._registry.get(name)

    def _log_result(self, result: ToolResult) -> None:

        if result.success:
            Logger.info(f"'{result.tool_name}' succeeded: {result.data}")
        elif result.metadata.get("clarification"):
            Logger.info(
                f"'{result.tool_name}' needs clarification: "
                f"{result.metadata.get('options')}"
            )
        else:
            Logger.warning(f"'{result.tool_name}' failed: {result.error}")