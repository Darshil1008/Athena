"""
Athena Search Tool

Fetches real web search results from DuckDuckGo for explicitly
triggered search queries, and via search() for queries the Planner
flags as needing current information even without a trigger phrase.

This version includes temporary diagnostic logging so we can inspect
exactly what the search backend returns before Gemma synthesizes it.
"""

import html
import re
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from core.logger import Logger

from ..base_tool import BaseTool
from ..tool_result import ToolResult


_TRIGGER_PATTERN = re.compile(
    r"^(?:search(?!\s+for\b)|look up|ask)[:\s]+(.+)",
    re.IGNORECASE,
)

MAX_RESULTS = 5
REQUEST_TIMEOUT = 10


class _DuckDuckGoParser(HTMLParser):
    """
    Parses DuckDuckGo result blocks without relying on one giant
    regular expression.
    """

    def __init__(self, max_results: int):
        super().__init__()

        self.max_results = max_results
        self.results: list[tuple[str, str, str]] = []

        self._in_result = False
        self._result_depth = 0

        self._in_title = False
        self._in_snippet = False

        self._current_url = ""
        self._current_title: list[str] = []
        self._current_snippet: list[str] = []

    @staticmethod
    def _classes(attrs):
        attributes = dict(attrs)
        return set(attributes.get("class", "").split())

    def handle_starttag(self, tag, attrs):

        if len(self.results) >= self.max_results:
            return

        classes = self._classes(attrs)
        attributes = dict(attrs)

        if "result" in classes and not self._in_result:

            self._in_result = True
            self._result_depth = 1

            self._current_url = ""
            self._current_title = []
            self._current_snippet = []

            return

        if not self._in_result:
            return

        self._result_depth += 1

        if tag == "a" and "result__a" in classes:

            self._in_title = True

            href = attributes.get("href", "")

            self._current_url = self._resolve_url(href)

        elif "result__snippet" in classes:

            self._in_snippet = True

    def handle_endtag(self, tag):

        if not self._in_result:
            return

        if tag == "a" and self._in_title:
            self._in_title = False

        if self._in_snippet and tag in {"a", "div"}:
            self._in_snippet = False

        self._result_depth -= 1

        if self._result_depth <= 0:
            self._finish_result()

    def handle_data(self, data):

        if not self._in_result:
            return

        if self._in_title:
            self._current_title.append(data)

        elif self._in_snippet:
            self._current_snippet.append(data)

    def _finish_result(self):

        title = self._clean_text(
            " ".join(self._current_title)
        )

        snippet = self._clean_text(
            " ".join(self._current_snippet)
        )

        url = self._current_url.strip()

        if title and url:
            self.results.append(
                (
                    title,
                    snippet,
                    url,
                )
            )

        self._in_result = False
        self._result_depth = 0

        self._in_title = False
        self._in_snippet = False

        self._current_url = ""
        self._current_title = []
        self._current_snippet = []

    @staticmethod
    def _clean_text(value: str) -> str:

        value = html.unescape(value)

        return re.sub(
            r"\s+",
            " ",
            value,
        ).strip()

    @staticmethod
    def _resolve_url(raw_url: str) -> str:

        if not raw_url:
            return ""

        raw_url = html.unescape(raw_url)

        if raw_url.startswith("//"):
            raw_url = "https:" + raw_url

        elif raw_url.startswith("/"):
            raw_url = urllib.parse.urljoin(
                "https://html.duckduckgo.com",
                raw_url,
            )

        parsed = urllib.parse.urlparse(raw_url)

        if parsed.path.rstrip("/") == "/l":

            params = urllib.parse.parse_qs(
                parsed.query
            )

            destination = params.get("uddg")

            if destination:
                return destination[0]

        return raw_url


class SearchTool(BaseTool):
    """
    Fetches current web search results for explicitly triggered
    queries, and for queries the Planner determines need current
    information even when no trigger phrase was used.
    """

    @property
    def name(self) -> str:
        return "search"

    @property
    def description(self) -> str:

        return (
            "Fetches current web search results for questions that "
            "need up-to-date information. Explicit trigger only: "
            "'search X', 'look up X', or 'ask X'. "
            "'search for X' opens a browser instead."
        )

    def can_handle(self, query: str) -> bool:

        return bool(
            _TRIGGER_PATTERN.match(
                query.strip()
            )
        )

    def execute(self, query: str) -> ToolResult:

        question = self._extract_question(query)

        if not question:

            return ToolResult(
                success=False,
                tool_name=self.name,
                error=(
                    "I couldn't tell what to search for."
                ),
            )

        return self.search(question)

    def search(self, question: str) -> ToolResult:
        """
        Run a search for an already-known question, bypassing the
        trigger-phrase gate in execute().

        Used by Athena to ground answers when the Planner flags a
        query as needing current information, even when no tool's
        trigger words matched (e.g. plain "what's the latest python
        version").
        """

        Logger.info(
            f"Search query: '{question}'"
        )

        try:

            results = self._fetch_results(
                question
            )

        except urllib.error.HTTPError as error:

            Logger.error(
                f"Search HTTP error: {error.code}"
            )

            return ToolResult(
                success=False,
                tool_name=self.name,
                error=(
                    f"The search engine returned "
                    f"HTTP {error.code}. "
                    "Please try again."
                ),
            )

        except urllib.error.URLError as error:

            Logger.error(
                f"Search connection error: {error}"
            )

            return ToolResult(
                success=False,
                tool_name=self.name,
                error=(
                    "I couldn't reach the search engine. "
                    "Please check the internet connection "
                    "and try again."
                ),
            )

        except TimeoutError:

            Logger.error(
                "Search request timed out."
            )

            return ToolResult(
                success=False,
                tool_name=self.name,
                error=(
                    "The search request timed out. "
                    "Please try again."
                ),
            )

        except OSError as error:

            Logger.error(
                f"Search OS error: {error}"
            )

            return ToolResult(
                success=False,
                tool_name=self.name,
                error=(
                    f"The search request failed: {error}"
                ),
            )

        if not results:

            Logger.warning(
                "Search returned zero usable results."
            )

            return ToolResult(
                success=False,
                tool_name=self.name,
                error=(
                    f"The search engine returned no "
                    f"usable results for '{question}'."
                ),
            )

        # ---------------------------------------------------------
        # TEMPORARY DIAGNOSTIC OUTPUT
        # ---------------------------------------------------------

        Logger.info(
            f"Search returned {len(results)} result(s)."
        )

        for index, (
            title,
            snippet,
            url,
        ) in enumerate(results, start=1):

            Logger.info(
                f"Search result {index}:"
            )

            Logger.info(
                f"  TITLE: {title}"
            )

            Logger.info(
                f"  SNIPPET: {snippet}"
            )

            Logger.info(
                f"  URL: {url}"
            )

        # ---------------------------------------------------------

        formatted = "\n\n".join(
            (
                f"{index}. {title}\n"
                f"Snippet: {snippet}\n"
                f"Source: {url}"
            )
            for index, (
                title,
                snippet,
                url,
            ) in enumerate(
                results,
                start=1,
            )
        )

        return ToolResult(
            success=True,
            tool_name=self.name,
            data=question,
            metadata={
                "needs_synthesis": True,
                "search_results": formatted,
            },
        )

    def _extract_question(
        self,
        query: str,
    ) -> str:

        match = _TRIGGER_PATTERN.match(
            query.strip()
        )

        if not match:
            return ""

        return match.group(1).strip()

    def _fetch_results(
        self,
        question: str,
    ) -> list[tuple[str, str, str]]:

        url = (
            "https://html.duckduckgo.com/html/?q="
            + urllib.parse.quote_plus(
                question
            )
        )

        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/142.0 Safari/537.36"
                ),
                "Accept": (
                    "text/html,"
                    "application/xhtml+xml"
                ),
                "Accept-Language": (
                    "en-US,en;q=0.9"
                ),
            },
        )

        with urllib.request.urlopen(
            request,
            timeout=REQUEST_TIMEOUT,
        ) as response:

            raw_html = response.read().decode(
                "utf-8",
                errors="ignore",
            )

        parser = _DuckDuckGoParser(
            MAX_RESULTS
        )

        parser.feed(raw_html)
        parser.close()

        return parser.results