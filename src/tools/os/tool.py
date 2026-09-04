"""
OS Tool for Athena.

Launches desktop applications: known system tools via a static
fast-path registry, and any other installed application via a
dynamic, cached AppIndex.
"""

import shutil
import subprocess
from pathlib import Path

from ..base_tool import BaseTool
from ..tool_result import ToolResult
from .app_index import AppIndex
from .applications import APPLICATIONS

LAUNCH_WORDS = ("open", "launch", "start", "run")

FILLER_WORDS = {
    "please", "the", "a", "an", "app", "application", "program",
    "for", "me", "up",
}


class OSTool(BaseTool):
    """
    Launches desktop applications installed on the system.
    """

    def __init__(self) -> None:
        self._app_index = AppIndex()
        # Each pending candidate is (display_name, identifier, is_path).
        self._pending_candidates: list[tuple[str, str, bool]] | None = None

    @property
    def name(self) -> str:
        return "os"

    @property
    def description(self) -> str:
        return "Launch desktop applications."

    def can_handle(self, query: str) -> bool:

        query = query.lower()

        if not any(word in query for word in LAUNCH_WORDS):
            return False

        return bool(self._extract_app_name(query))

    def execute(self, query: str) -> ToolResult:

        query = query.lower()

        # Fast path: known system tools / curated aliases. These are
        # always bare command names resolved via PATH (shutil.which).
        for app in APPLICATIONS.values():
            if any(alias in query for alias in app["aliases"]):
                return self._launch_classic(
                    app["command"], app["display_name"]
                )

        # Dynamic path: search the installed-application index.
        app_name = self._extract_app_name(query)

        if not app_name:
            return ToolResult(
                success=False,
                tool_name=self.name,
                error="I couldn't tell which application to open.",
            )

        matches = self._app_index.search(app_name)

        if not matches:
            return ToolResult(
                success=False,
                tool_name=self.name,
                error=(
                    f"Couldn't find an installed application matching "
                    f"'{app_name}'."
                ),
            )

        if len(matches) == 1:
            display_name, identifier, is_path = matches[0]
            return self._launch_resolved(identifier, display_name, is_path)

        # Multiple plausible matches — ask, don't guess.
        self._pending_candidates = matches[:5]

        return ToolResult(
            success=False,
            tool_name=self.name,
            metadata={
                "clarification": True,
                "options": [name for name, _, _ in self._pending_candidates],
            },
        )

    # ------------------------------------------------------------------
    # Clarification support (see BaseTool)
    # ------------------------------------------------------------------

    def has_pending_clarification(self) -> bool:
        return self._pending_candidates is not None

    def resolve_clarification(self, user_input: str) -> ToolResult:

        candidates = self._pending_candidates
        self._pending_candidates = None  # clear regardless of outcome

        if candidates is None:
            return ToolResult(
                success=False,
                tool_name=self.name,
                error="No pending application selection.",
            )

        selection = user_input.strip()
        chosen_index = None

        if selection.isdigit():
            index = int(selection) - 1
            if 0 <= index < len(candidates):
                chosen_index = index

        if chosen_index is None:
            return ToolResult(
                success=False,
                tool_name=self.name,
                error=(
                    "That wasn't one of the options, so I've cancelled "
                    "the request. Feel free to ask again."
                ),
            )

        display_name, identifier, is_path = candidates[chosen_index]
        return self._launch_resolved(identifier, display_name, is_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_app_name(self, query: str) -> str:
        """
        Pull the application name out of a query like "open visual
        studio code please" -> "visual studio code".
        """

        tokens = query.split()
        remainder: list[str] = []

        for i, token in enumerate(tokens):
            if token in LAUNCH_WORDS:
                remainder = tokens[i + 1:]
                break

        remainder = [t for t in remainder if t not in FILLER_WORDS]

        return " ".join(remainder).strip()

    def _launch_resolved(
        self, identifier: str, display_name: str, is_path: bool
    ) -> ToolResult:
        """
        Launch an identifier that came from AppIndex, which already
        determined (by checking real file existence at index-build
        time) whether it's a genuine executable path or an opaque
        AppUserModelID.
        """

        if is_path:
            return self._launch_classic([identifier], display_name)

        return self._launch_via_shell_apps_folder(identifier, display_name)

    def _launch_classic(
        self, command: list[str], display_name: str
    ) -> ToolResult:
        """
        Launch a real executable directly.

        - If command[0] is already an absolute path (from AppIndex,
          confirmed to exist), use it directly.
        - Otherwise (static registry entries like "notepad"), resolve
          it via shutil.which() so PATH-based lookups (including
          Windows .cmd/.bat shims) work correctly.
        - shell=False throughout: process creation talks directly to
          the OS, so failures raise a real, catchable exception
          instead of failing silently inside a hidden shell process.
        """

        exe = command[0]

        if not Path(exe).is_absolute():
            resolved = shutil.which(exe)

            if resolved is None:
                return ToolResult(
                    success=False,
                    tool_name=self.name,
                    error=(
                        f"Could not find '{exe}' on this system. "
                        f"Is {display_name} installed and on PATH?"
                    ),
                )

            exe = resolved

        resolved_command = [exe, *command[1:]]

        try:
            subprocess.Popen(resolved_command, shell=False)

        except (OSError, ValueError) as error:
            return ToolResult(
                success=False,
                tool_name=self.name,
                error=f"OS Tool Error: Failed to launch {display_name} ({error}).",
            )

        return ToolResult(
            success=True,
            tool_name=self.name,
            data=f"Launching {display_name}...",
        )

    def _launch_via_shell_apps_folder(
        self, app_id: str, display_name: str
    ) -> ToolResult:
        """
        Activate an app via Explorer's shell:AppsFolder protocol.

        Required for any app whose Get-StartApps AppID is NOT a real
        file path -- this covers UWP/Store apps (PackageFamilyName!AppID)
        as well as classic apps that register a custom AppUserModelID
        (common with Electron/Squirrel-based installers: Brave,
        Discord, Slack, etc). Windows refuses to CreateProcess these
        directly ("the process has no package identity").
        """

        try:
            subprocess.Popen(
                ["explorer.exe", f"shell:AppsFolder\\{app_id}"],
                shell=False,
            )

        except OSError as error:
            return ToolResult(
                success=False,
                tool_name=self.name,
                error=f"OS Tool Error: Failed to launch {display_name} ({error}).",
            )

        return ToolResult(
            success=True,
            tool_name=self.name,
            data=f"Launching {display_name}...",
        )