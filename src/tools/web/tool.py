"""
Web Tool for Athena.

Opens URLs and runs web searches using the system's default browser.
Deterministic -- no LLM involved, per Athena's engineering principle
that reach-type actions (opening things) should bypass Gemma
whenever possible.
"""

import re
import webbrowser
from urllib.parse import quote_plus

from ..base_tool import BaseTool
from ..tool_result import ToolResult

OPEN_WORDS = ("open", "go to", "visit", "browse to", "browse")
# NOTE: bare "search" and "look up" were deliberately removed from
# here -- they now belong to SearchTool (answer it), which is more
# forgiving than the colon-syntax it replaced. "search for"/"look
# for" keep their original meaning: open a browser and show results.
SEARCH_WORDS = ("search for", "google", "look for")

# Loose domain-shape check: something.tld, optionally with a path.
# Enough to tell "open google.com" apart from "open notepad" without
# needing a full URL grammar.
_DOMAIN_PATTERN = re.compile(
    r"^(https?://)?(www\.)?[a-z0-9-]+(\.[a-z0-9-]+)+(/\S*)?$"
)


class WebTool(BaseTool):
    """
    Opens URLs and runs web searches via the system's default browser.
    """

    @property
    def name(self) -> str:
        return "web"

    @property
    def description(self) -> str:
        return "Open websites and run web searches in the default browser."

    def can_handle(self, query: str) -> bool:

        query = query.lower().strip()

        if self._extract_search_query(query) is not None:
            return True

        return self._extract_url(query) is not None

    def execute(self, query: str) -> ToolResult:

        query = query.lower().strip()

        search_query = self._extract_search_query(query)

        if search_query is not None:
            url = f"https://www.google.com/search?q={quote_plus(search_query)}"
            return self._open(url, f"a search for '{search_query}'")

        url = self._extract_url(query)

        if url is not None:
            return self._open(url, url)

        return ToolResult(
            success=False,
            tool_name=self.name,
            error="I couldn't figure out what to open or search for.",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_search_query(self, query: str) -> str | None:
        """
        Detect explicit search intent ("search for X", "google X",
        "look up X") and return the search terms, or None if this
        isn't a search request.
        """

        for phrase in SEARCH_WORDS:

            prefix = phrase + " "
            if query.startswith(prefix):
                return query[len(prefix):].strip() or None

            marker = f" {phrase} "
            if marker in query:
                return query.split(marker, 1)[1].strip() or None

        return None

    def _extract_url(self, query: str) -> str | None:
        """
        Pull a URL-shaped token out of the query and normalize it
        with a scheme, or return None if nothing URL-like is present.
        """

        remainder = query

        for phrase in OPEN_WORDS:
            marker = phrase + " "
            idx = query.find(marker)

            if idx != -1:
                remainder = query[idx + len(phrase):].strip()
                break

        if not remainder:
            return None

        candidate = remainder.split()[0]

        if not _DOMAIN_PATTERN.match(candidate):
            return None

        if not candidate.startswith(("http://", "https://")):
            candidate = f"https://{candidate}"

        return candidate

    def _open(self, url: str, description: str) -> ToolResult:

        try:
            opened = webbrowser.open(url)

        except Exception as error:
            return ToolResult(
                success=False,
                tool_name=self.name,
                error=(
                    f"Web Tool Error: Failed to open {description} "
                    f"({error})."
                ),
            )

        if not opened:
            return ToolResult(
                success=False,
                tool_name=self.name,
                error=f"Couldn't find a browser to open {description} with.",
            )

        return ToolResult(
            success=True,
            tool_name=self.name,
            data=f"Opening {description}...",
        )