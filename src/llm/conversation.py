"""
Athena Conversation Manager

Responsible only for managing the conversation between
the user and Athena.
"""

import time
from typing import TYPE_CHECKING

from prompt.prompt_manager import PromptManager

if TYPE_CHECKING:
    from core.assistant import Athena


class ConversationManager:
    """
    Manages conversation history and terminal chat.
    """

    def __init__(self, athena: "Athena"):

        self.athena = athena

        self.history = [
            {
                "role": "system",
                "content": PromptManager.build_prompt()
            }
        ]

    def chat(self):
        """
        Start the terminal chat loop.
        """

        print("\n========================================")
        print("Athena is ready!")
        print("Type 'exit' to quit.")
        print("========================================\n")

        while True:

            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "bye"):
                print("\nAthena: Goodbye!\n")
                break

            self.history.append(
                {
                    "role": "user",
                    "content": user_input
                }
            )

            print("\nAthena is thinking...", end="", flush=True)

            start_time = time.perf_counter()

            response = self.athena.process_request(
                user_input,
                self.history
            )

            end_time = time.perf_counter()
            response_time = end_time - start_time

            print("\r" + " " * 80 + "\r", end="", flush=True)

            self.history.append(
                {
                    "role": "assistant",
                    "content": response
                }
            )

            print(f"Athena ({response_time:.2f}s): {response}\n")