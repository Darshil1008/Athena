"""
Tool registry for Athena.

The registry keeps track of all available tools.
"""

from typing import Dict, List

from .base_tool import BaseTool


class ToolRegistry:
    """
    Registers and manages Athena tools.
    """

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """
        Register a new tool.

        Raises:
            ValueError: If a tool with the same name already exists.
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered.")

        self._tools[tool.name] = tool

    def unregister(self, tool_name: str) -> None:
        """
        Remove a tool from the registry.
        """
        self._tools.pop(tool_name, None)

    def get(self, tool_name: str) -> BaseTool | None:
        """
        Return a tool by name.
        """
        return self._tools.get(tool_name)

    def list_tools(self) -> List[BaseTool]:
        """
        Return all registered tools.
        """
        return list(self._tools.values())