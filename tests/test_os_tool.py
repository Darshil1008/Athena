"""
Tests for OSTool's routing and launch-branching logic.

subprocess.Popen and AppIndex are mocked throughout -- these tests
must never actually launch a process or shell out to PowerShell.
"""

from unittest.mock import MagicMock, patch

import pytest

from tools.os.tool import OSTool


@pytest.fixture
def tool():
    with patch("tools.os.tool.AppIndex") as mock_index_cls:
        instance = OSTool()
        instance._app_index = mock_index_cls.return_value
        yield instance


class TestCanHandle:

    def test_accepts_static_alias(self, tool):
        assert tool.can_handle("open notepad") is True

    def test_accepts_arbitrary_app_name(self, tool):
        assert tool.can_handle("open some random app") is True

    def test_rejects_query_without_launch_word(self, tool):
        assert tool.can_handle("notepad is great") is False

    def test_rejects_launch_word_with_nothing_after_it(self, tool):
        assert tool.can_handle("please open") is False


class TestExecuteStaticFastPath:

    def test_launches_static_app_via_which(self, tool):
        with patch(
            "tools.os.tool.shutil.which",
            return_value="C:\\Windows\\notepad.exe",
        ), patch("tools.os.tool.subprocess.Popen") as mock_popen:
            result = tool.execute("open notepad")

        assert result.success is True
        mock_popen.assert_called_once()

    def test_static_app_not_on_path_fails_cleanly(self, tool):
        with patch("tools.os.tool.shutil.which", return_value=None):
            result = tool.execute("open notepad")

        assert result.success is False
        assert "notepad" in result.error.lower()


class TestExecuteDynamicPath:

    def test_single_match_launches_directly(self, tool):
        tool._app_index.search.return_value = [
            ("Brave Browser", "BraveSoftware.BraveBrowser", False)
        ]

        with patch("tools.os.tool.subprocess.Popen") as mock_popen:
            result = tool.execute("open brave")

        assert result.success is True
        # UWP/AUMID path goes through explorer.exe shell:AppsFolder
        args = mock_popen.call_args[0][0]
        assert args[0] == "explorer.exe"
        assert "BraveSoftware.BraveBrowser" in args[1]

    def test_single_match_with_real_path_launches_directly(self, tool):
        tool._app_index.search.return_value = [
            ("Some App", "C:\\Program Files\\SomeApp\\app.exe", True)
        ]

        with patch("tools.os.tool.subprocess.Popen") as mock_popen:
            result = tool.execute("open some app")

        assert result.success is True
        args = mock_popen.call_args[0][0]
        assert args[0] == "C:\\Program Files\\SomeApp\\app.exe"

    def test_no_matches_fails_cleanly(self, tool):
        tool._app_index.search.return_value = []

        result = tool.execute("open zzzznotarealapp")

        assert result.success is False
        assert "couldn't find" in result.error.lower()

    def test_multiple_matches_asks_for_clarification(self, tool):
        tool._app_index.search.return_value = [
            ("VS Code", "C:\\vscode.exe", True),
            ("VS Code Insiders", "C:\\vscode-insiders.exe", True),
        ]

        # "myeditor" deliberately doesn't collide with any static
        # alias substring (e.g. "code", "calc", "cmd") so this
        # actually exercises the mocked dynamic path.
        result = tool.execute("open myeditor")

        assert result.success is False
        assert result.metadata.get("clarification") is True
        assert result.metadata.get("options") == ["VS Code", "VS Code Insiders"]
        assert tool.has_pending_clarification() is True


class TestClarificationResolution:

    def test_valid_selection_launches_chosen_app(self, tool):
        tool._pending_candidates = [
            ("VS Code", "C:\\vscode.exe", True),
            ("VS Code Insiders", "C:\\vscode-insiders.exe", True),
        ]

        with patch("tools.os.tool.subprocess.Popen") as mock_popen:
            result = tool.resolve_clarification("2")

        assert result.success is True
        args = mock_popen.call_args[0][0]
        assert args[0] == "C:\\vscode-insiders.exe"
        assert tool.has_pending_clarification() is False

    def test_invalid_selection_cancels_cleanly(self, tool):
        tool._pending_candidates = [
            ("VS Code", "C:\\vscode.exe", True),
        ]

        result = tool.resolve_clarification("banana")

        assert result.success is False
        assert tool.has_pending_clarification() is False