"""
Athena Planner.

The Planner is responsible for determining what the user is trying
to accomplish. It asks Gemma to classify the query into a structured
Plan. It does not execute tools or perform system actions.

If the LLM is unavailable, slow to respond usefully, or returns
something that isn't valid/parsable, create_plan() falls back to a
safe task_type="unknown" Plan rather than raising or guessing —
Athena must never claim to understand something it didn't.
"""

import json
import re

from llm.client import LLMClient
from .plan import Plan


_SYSTEM_PROMPT = """You are the intent classifier for a local assistant called Athena.

Given a single user message, respond with ONLY a JSON object (no markdown, no
explanation, no code fences) with exactly these fields:

{
  "task_type": one of ["conversation", "information", "research", "verification", "file", "application", "system", "multi_step", "unknown"],
  "goal": a short restatement of what the user wants,
  "requires_reasoning": true or false,
  "requires_current_information": true or false,
  "steps": a list of short strings describing the steps needed (can be empty),
  "confidence": a number between 0.0 and 1.0
}

Rules:
- "search" is never a task_type. Web search is an internal capability, not a task type.
- If the user is just chatting or greeting, use "conversation".
- If the answer could change over time (current events, latest versions, prices,
  who currently holds a position), set requires_current_information to true.
- If the user asks you to verify or fact-check a claim, use "verification" and set
  both requires_reasoning and requires_current_information to true.
- If the user wants a file found and/or read, use "file".
- If the user wants an application opened, closed, or controlled, use "application".
- If the request has multiple distinct parts (e.g. find a file AND summarize it),
  use "multi_step".
- If you are not confident what the user wants, use "unknown" and set confidence low.

Respond with the JSON object only."""


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"```$", "", text)
    return text.strip()


def _fallback_plan(query: str) -> Plan:
    return Plan(
        task_type="unknown",
        goal=query if query else "No user goal provided.",
        confidence=0.0,
    )


class Planner:
    """
    Athena's intent and planning layer.

    Sprint 4.1 introduced the Plan contract. This version (Sprint 4.2)
    uses Gemma directly to classify every query into a Plan — no
    rule-based fast path yet. That's a deliberate tradeoff of speed
    for correctness, made by choice, and can be revisited later
    without changing this class's public interface (create_plan
    still takes a string and returns a Plan).
    """

    def __init__(self, llm_client: LLMClient) -> None:
        """
        Initialize the Planner.

        Args:
            llm_client: An existing LLMClient instance, injected
                rather than constructed here, matching Athena's
                dependency-injection pattern.
        """
        self.llm_client = llm_client

    def create_plan(self, query: str) -> Plan:
        """
        Create a Plan for a user query by asking Gemma to classify it.

        Never raises due to a bad or missing LLM response — falls
        back to a safe task_type="unknown" Plan instead.
        """

        if not isinstance(query, str):
            raise TypeError("Planner query must be a string.")

        query = query.strip()

        if not query:
            return _fallback_plan(query)

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ]

        raw = self.llm_client.generate(messages, temperature=0.1, format="json")

        if raw.startswith("[Ollama Error]") or raw.startswith("[Connection Error]"):
            return _fallback_plan(query)

        cleaned = _strip_code_fences(raw)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return _fallback_plan(query)

        try:
            return Plan(
                task_type=data.get("task_type", "unknown"),
                goal=data.get("goal") or query,
                requires_reasoning=bool(data.get("requires_reasoning", False)),
                requires_current_information=bool(
                    data.get("requires_current_information", False)
                ),
                steps=list(data.get("steps", [])),
                confidence=float(data.get("confidence", 0.0)),
            )
        except (ValueError, TypeError):
            return _fallback_plan(query)