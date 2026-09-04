"""
Athena LLM Client

Responsible only for communicating with the Ollama server.
"""

from ollama import Client, ResponseError

from core import config


class LLMClient:
    """Handles communication with the local Ollama server."""

    def __init__(self):
        self.client = Client(host=config.OLLAMA_HOST)

    def generate(
        self,
        messages: list[dict],
        temperature: float | None = None,
        format: str | None = None,
    ) -> str:
        """
        Send messages to Ollama and return the assistant's reply.

        Args:
            messages:
                Conversation history in Ollama chat format.

            temperature:
                Optional per-request temperature override.
                If omitted, the application's default temperature
                from config.py is used.

            format:
                Optional response format constraint (e.g. "json" to
                force Ollama to return valid JSON). Defaults to None,
                which preserves existing free-text behavior for all
                current callers.

        Returns:
            Assistant response as plain text.
        """

        if temperature is None:
            temperature = config.TEMPERATURE

        try:
            response = self.client.chat(
                model=config.MODEL,
                messages=messages,
                format=format,
                options={
                    "temperature": temperature,
                },
            )

            return response["message"]["content"]

        except ResponseError as error:
            return f"[Ollama Error] {error}"

        except Exception as error:
            return f"[Connection Error] {error}"