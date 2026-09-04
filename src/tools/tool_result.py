from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(slots=True)
class ToolResult:
    """
    Standard response object returned by every Athena tool.
    """

    success: bool
    tool_name: str

    data: Any = None
    error: str | None = None

    metadata: Dict[str, Any] = field(default_factory=dict)