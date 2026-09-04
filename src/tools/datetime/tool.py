"""
Date & Time tool for Athena.
"""

import re
from datetime import datetime

from ..base_tool import BaseTool
from ..tool_result import ToolResult

# Whole-word matching, not substring matching. Plain substring checks
# (e.g. "day" in query) false-positive on words like "birthday",
# "Monday", "yesterday", "payday" -- hijacking unrelated messages into
# a date/time response instead of passing them through. This is a
# contained bug fix, not the Intent Router the handbook already
# tracks as separate future work.
_KEYWORD_PATTERNS = {
    "time": re.compile(r"\btime\b"),
    "date": re.compile(r"\bdate\b"),
    "today": re.compile(r"\btoday\b"),
    "day": re.compile(r"\bday\b"),
    "weekday": re.compile(r"\bweekday\b"),
    "what_day": re.compile(r"\bwhat day\b"),
}


class DateTimeTool(BaseTool):
    """
    Provides the current date, time, and day.
    """

    @property
    def name(self) -> str:
        return "datetime"

    @property
    def description(self) -> str:
        return "Returns the current date and time."

    def can_handle(self, query: str) -> bool:
        """
        Determine whether this tool should handle the query.
        """

        query = query.lower()

        return any(
            pattern.search(query) for pattern in _KEYWORD_PATTERNS.values()
        )

    def execute(self, query: str) -> ToolResult:
        """
        Execute the requested date/time operation.
        """

        query = query.lower()
        now = datetime.now()

        if _KEYWORD_PATTERNS["time"].search(query):
            result = now.strftime("%I:%M:%S %p")

        elif (
            _KEYWORD_PATTERNS["date"].search(query)
            or _KEYWORD_PATTERNS["today"].search(query)
        ):
            result = now.strftime("%d %B %Y")

        elif (
            _KEYWORD_PATTERNS["weekday"].search(query)
            or _KEYWORD_PATTERNS["what_day"].search(query)
        ):
            result = now.strftime("%A")

        else:
            result = (
                f"Date : {now.strftime('%d %B %Y')}\n"
                f"Time : {now.strftime('%I:%M:%S %p')}\n"
                f"Day  : {now.strftime('%A')}"
            )

        return ToolResult(
            success=True,
            tool_name=self.name,
            data=result,
        )