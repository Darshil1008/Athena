"""
Base interface for all Athena tools.

Every tool must inherit from BaseTool and implement
the required methods.
"""

from abc import ABC, abstractmethod

from .tool_result import ToolResult


class BaseTool(ABC):
    """
    Abstract base class for every Athena tool.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name of the tool."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Short description of the tool."""
        pass

    @abstractmethod
    def can_handle(self, query: str) -> bool:
        """
        Return True if this tool can handle the given query.
        """
        pass

    @abstractmethod
    def execute(self, query: str) -> ToolResult:
        """
        Execute the tool and return a ToolResult.
        """
        pass

    # ------------------------------------------------------------------
    # Optional: multi-turn clarification support.
    #
    # A tool MAY need a follow-up answer from the user before it can
    # finish a request (e.g. "which of these 3 apps did you mean?").
    # Default implementations are no-ops so existing tools (Calculator,
    # DateTime) require no changes to keep working exactly as before.
    # ------------------------------------------------------------------

    def has_pending_clarification(self) -> bool:
        """
        Return True if this tool is mid-conversation, waiting on a
        clarifying answer from the user before it can proceed.
        """
        return False

    def resolve_clarification(self, user_input: str) -> ToolResult:
        """
        Resume a previously started request using the user's answer
        to a clarifying question. Only called when
        has_pending_clarification() is True.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support clarification."
        )