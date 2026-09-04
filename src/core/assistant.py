"""
Core class for Project Athena.
"""

from datetime import date

from core import config
from core.logger import Logger

from llm.client import LLMClient
from llm.conversation import ConversationManager

from tools.manager import ToolManager

from planner.planner import Planner


class Athena:
    """
    Main Athena application.
    """

    def __init__(self, tool_manager: ToolManager):

        self.name = config.NAME
        self.version = config.VERSION

        self.client = LLMClient()
        self.tool_manager = tool_manager

        self.planner = Planner(self.client)

        self.conversation = ConversationManager(self)

    def display_banner(self):

        print("=" * 50)
        print(f"          {self.name} v{self.version}")
        print("      Local AI Desktop Assistant")
        print("=" * 50)

    def process_request(
        self,
        user_input: str,
        history: list[dict],
    ) -> str:

        # Sprint 4.3: the Planner runs on every request. Sprint 4.4
        # starts acting on its output: when nothing else handles the
        # query and the Planner says it needs current information,
        # ground the answer in real search instead of letting Gemma
        # guess from memory.
        plan = self.planner.create_plan(user_input)
        Logger.info(f"Plan: {plan}")

        tool_result = self.tool_manager.execute(user_input)

        if tool_result.success:

            # Search results are evidence, not the final answer.
            # They must be synthesized by Gemma using the grounding
            # rules defined in _synthesize_from_search().
            if tool_result.metadata.get("needs_synthesis"):
                return self._synthesize_from_search(
                    tool_result,
                    history,
                )

            return str(tool_result.data)

        # Ambiguous match — present deterministic tool options
        # directly instead of asking the LLM to improvise.
        if tool_result.metadata.get("clarification"):

            options = tool_result.metadata.get("options", [])

            listing = "\n".join(
                f"{i + 1}. {name}"
                for i, name in enumerate(options)
            )

            return (
                "I found a few matches — which one did you mean?\n"
                f"{listing}"
            )

        # No tool matched.
        if tool_result.tool_name == "ToolManager":

            # If the Planner says this needs current information,
            # ground the answer in real search results instead of
            # letting Gemma guess from memory (which hallucinates,
            # as seen with "what's the latest python version").
            if plan.requires_current_information:

                search_tool = self.tool_manager.get_tool("search")

                if search_tool is not None:
                    search_result = search_tool.search(plan.goal or user_input)

                    if search_result.success and search_result.metadata.get("needs_synthesis"):
                        return self._synthesize_from_search(search_result, history)

            # Ordinary conversation, or search unavailable/failed —
            # fall back to the normal LLM path.
            return self.client.generate(history)

        # A real tool matched but failed.
        #
        # The LLM is informed of the failure so it does not claim
        # that an action was successfully completed.
        grounded_history = history + [
            {
                "role": "system",
                "content": (
                    "A tool was attempted for the user's last message "
                    f"and failed: {tool_result.error}\n\n"
                    "Do not claim that the requested action was "
                    "completed. Tell the user honestly that it failed "
                    "and briefly explain why."
                ),
            }
        ]

        return self.client.generate(grounded_history)

    def _synthesize_from_search(
        self,
        tool_result,
        history: list[dict],
    ) -> str:
        """
        Synthesize an answer from retrieved web search results.

        Search results are treated as the primary evidence for
        current-information questions. Gemma's pretrained knowledge
        must not override retrieved evidence.
        """

        question = tool_result.data

        search_results = tool_result.metadata.get(
            "search_results",
            "",
        )

        current_date = date.today().isoformat()

        grounding_prompt = f"""
You are Athena answering a user using freshly retrieved web
search results.

CURRENT DATE:
{current_date}

USER QUESTION:
{question}

WEB SEARCH RESULTS:
{search_results}

GROUNDING RULES:

1. Use the retrieved web results as the primary evidence.

2. For questions containing words such as:
   - latest
   - current
   - today
   - now
   - newest
   - recently

   prioritize the newest reliable information present in the
   retrieved results.

3. Do NOT substitute your pretrained knowledge for information
   contained in the retrieved results.

4. A publication date, release date, article date, or page date
   is NOT automatically today's date.

5. Never invent a date, fact, source, URL, or search result.

6. Prefer official or authoritative sources when they are present.

7. If the retrieved results genuinely do not establish the answer,
   say that clearly rather than guessing.

8. If sources disagree, acknowledge the disagreement rather than
   silently choosing an unsupported answer.

9. Answer the user's actual question directly. Do not discuss
   these grounding instructions.

10. Keep the response concise unless additional explanation is
    genuinely useful.

Return only the answer that should be shown to the user.
""".strip()

        # We deliberately use only the system prompt plus the user's
        # question here instead of replaying the entire conversation.
        #
        # This reduces redundant context and keeps search synthesis
        # focused on the retrieved evidence.
        synthesis_messages = [
            {
                "role": "system",
                "content": grounding_prompt,
            },
            {
                "role": "user",
                "content": question,
            },
        ]

        return self.client.generate(
            synthesis_messages,
            temperature=0.2,
        )

    def run(self):

        self.display_banner()

        Logger.info("Initializing Athena Core...")
        Logger.info("Loading configuration...")
        Logger.info("Logger initialized.")
        Logger.info("Athena started successfully.")

        self.conversation.chat()