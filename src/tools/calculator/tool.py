"""
Calculator tool for Athena.
"""

import re

from ..base_tool import BaseTool
from ..tool_result import ToolResult

from .evaluator import SafeEvaluator

class CalculatorTool(BaseTool):
    """
    Performs safe mathematical calculations.
    """

    def __init__(self):
        self._evaluator = SafeEvaluator()

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return "Safely evaluates mathematical expressions."

    def can_handle(self, query: str) -> bool:
        """
        Detect whether a query looks like a mathematical expression.
        """

        pattern = r"^[0-9\s+\-*/().%]+$"

        return bool(re.fullmatch(pattern, query.strip()))

    def execute(self, query: str) -> ToolResult:

        try:

            result = self._evaluator.evaluate(query)

            return ToolResult(
                success=True,
                tool_name=self.name,
                data=result
            )

        except Exception as e:

            return ToolResult(
                success=False,
                tool_name=self.name,
                error=str(e)
            )