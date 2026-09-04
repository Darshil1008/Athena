"""
File Tool for Athena.

Finds files by name and reads their text content. Deterministic, no
LLM involved. Read-only in this version -- write/delete are
explicitly out of scope for now (may be added in a future sprint).
"""

from pathlib import Path

from ..base_tool import BaseTool
from ..tool_result import ToolResult

FIND_WORDS = ("find", "search for", "look for", "locate")
READ_WORDS = ("read", "show me", "what's in", "display", "cat ")

# Default roots to search when the user doesn't give a full path --
# scanning the entire filesystem would be slow and would surface
# irrelevant system files. These cover where a typical user actually
# keeps their own files.
DEFAULT_SEARCH_ROOTS = [
    Path.home() / "Desktop",
    Path.home() / "Documents",
    Path.home() / "Downloads",
]

MAX_SEARCH_RESULTS = 10
MAX_FILES_SCANNED = 20000  # safety cap so a huge drive can't hang the tool
MAX_READ_BYTES = 200_000   # ~200 KB; larger files are truncated, not fully loaded


class FileTool(BaseTool):
    """
    Finds files by name and reads their text content.
    """

    @property
    def name(self) -> str:
        return "files"

    @property
    def description(self) -> str:
        return "Find files by name and read their text content."

    def can_handle(self, query: str) -> bool:

        query = query.lower()

        if "file" not in query:
            return False

        return any(w in query for w in FIND_WORDS) or any(
            w in query for w in READ_WORDS
        )

    def execute(self, query: str) -> ToolResult:

        lowered = query.lower()

        if any(w in lowered for w in READ_WORDS):
            return self._read(query)

        return self._find(query)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def _read(self, query: str) -> ToolResult:

        target = self._extract_target(query, READ_WORDS)

        if not target:
            return ToolResult(
                success=False,
                tool_name=self.name,
                error="I couldn't tell which file to read.",
            )

        path = Path(target).expanduser()

        if not path.is_absolute() or not path.exists():
            # Not a usable path as typed -- try to locate it by name
            # under the default search roots first.
            matches = self._search(path.name or target)

            if not matches:
                return ToolResult(
                    success=False,
                    tool_name=self.name,
                    error=f"Couldn't find a file matching '{target}'.",
                )

            if len(matches) > 1:
                return ToolResult(
                    success=False,
                    tool_name=self.name,
                    error=(
                        f"Found multiple files matching '{target}': "
                        + ", ".join(str(m) for m in matches[:5])
                        + ". Please give a more specific name or full path."
                    ),
                )

            path = matches[0]

        if not path.is_file():
            return ToolResult(
                success=False,
                tool_name=self.name,
                error=f"'{path}' is not a readable file.",
            )

        try:
            raw = path.read_bytes()
        except OSError as error:
            return ToolResult(
                success=False,
                tool_name=self.name,
                error=f"Couldn't read '{path}': {error}",
            )

        truncated = len(raw) > MAX_READ_BYTES
        raw = raw[:MAX_READ_BYTES]

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return ToolResult(
                success=False,
                tool_name=self.name,
                error=f"'{path}' doesn't look like a text file I can read.",
            )

        if truncated:
            text += "\n\n[...truncated, file is larger than 200 KB...]"

        return ToolResult(
            success=True,
            tool_name=self.name,
            data=text,
            metadata={"path": str(path)},
        )

    # ------------------------------------------------------------------
    # Find
    # ------------------------------------------------------------------

    def _find(self, query: str) -> ToolResult:

        target = self._extract_target(query, FIND_WORDS)

        if not target:
            return ToolResult(
                success=False,
                tool_name=self.name,
                error="I couldn't tell what file to look for.",
            )

        matches = self._search(target)

        if not matches:
            return ToolResult(
                success=False,
                tool_name=self.name,
                error=f"Couldn't find a file matching '{target}'.",
            )

        listing = "\n".join(f"- {m}" for m in matches)

        return ToolResult(
            success=True,
            tool_name=self.name,
            data=f"Found {len(matches)} match(es):\n{listing}",
            metadata={"paths": [str(m) for m in matches]},
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_target(
        self, query: str, action_words: tuple[str, ...]
    ) -> str:
        """
        Pull the filename/search term out of a query like "find file
        report.pdf" -> "report.pdf", stripping the leading action
        phrase and a leading "file(s)"/"named"/"called".
        """

        lowered = query.lower()
        remainder = query

        for phrase in action_words:
            idx = lowered.find(phrase)
            if idx != -1:
                remainder = query[idx + len(phrase):].strip()
                break

        for filler in (
            "file named", "files named", "file called", "files called",
            "file", "files", "named", "called",
        ):
            if remainder.lower().startswith(filler + " "):
                remainder = remainder[len(filler):].strip()
                break

        return remainder.strip()

    def _search(self, name: str) -> list[Path]:
        """
        Search DEFAULT_SEARCH_ROOTS for files whose name contains
        `name` (case-insensitive). Capped in both breadth (files
        scanned) and results, so a huge drive can't hang the tool.
        """

        name = name.lower()
        matches: list[Path] = []
        scanned = 0

        for root in DEFAULT_SEARCH_ROOTS:

            if not root.exists():
                continue

            for path in root.rglob("*"):

                scanned += 1
                if scanned > MAX_FILES_SCANNED:
                    return matches[:MAX_SEARCH_RESULTS]

                if not path.is_file():
                    continue

                if name in path.name.lower():
                    matches.append(path)

                    if len(matches) >= MAX_SEARCH_RESULTS:
                        return matches

        return matches