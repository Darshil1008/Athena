"""
Structured planning models for Athena.

This module defines the Plan object produced by the planning layer.
The Plan describes what Athena believes the user wants to accomplish.
It does not execute anything.
"""

from dataclasses import dataclass, field
from typing import List


TASK_TYPES = {
    "conversation",
    "information",
    "research",
    "verification",
    "file",
    "application",
    "system",
    "multi_step",
    "unknown",
}


@dataclass
class Plan:
    """
    Structured representation of Athena's intended task.

    The Planner creates this object.
    Execution layers consume it later.

    The Plan itself must never execute tools or system actions.
    """

    task_type: str
    goal: str

    requires_reasoning: bool = False
    requires_current_information: bool = False

    steps: List[str] = field(default_factory=list)

    confidence: float = 0.0

    def __post_init__(self) -> None:
        """Validate the Plan after initialization."""

        if self.task_type not in TASK_TYPES:
            raise ValueError(
                f"Invalid task_type '{self.task_type}'. "
                f"Expected one of: {sorted(TASK_TYPES)}"
            )

        if not isinstance(self.goal, str) or not self.goal.strip():
            raise ValueError("Plan goal must be a non-empty string.")

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                "Plan confidence must be between 0.0 and 1.0."
            )

        if not isinstance(self.requires_reasoning, bool):
            raise TypeError("requires_reasoning must be a boolean.")

        if not isinstance(self.requires_current_information, bool):
            raise TypeError(
                "requires_current_information must be a boolean."
            )

        if not isinstance(self.steps, list):
            raise TypeError("steps must be a list.")

        if not all(isinstance(step, str) and step.strip() for step in self.steps):
            raise ValueError(
                "Every planning step must be a non-empty string."
            )