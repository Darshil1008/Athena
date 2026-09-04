"""
Tests for WebTool's URL and search-query detection logic.

open()/webbrowser calls are mocked -- these tests verify routing and
extraction logic only, not that a browser actually launches.
"""

from unittest.mock import patch

import pytest

from tools.web.tool import WebTool


@pytest.fixture
def tool():
    return WebTool()


class TestCanHandle:

    def test_accepts_domain_with_open(self, tool):
        assert tool.can_handle("open google.com") is True

    def test_accepts_domain_with_go_to(self, tool):
        assert tool.can_handle("go to youtube.com") is True

    def test_accepts_search_phrase(self, tool):
        assert tool.can_handle("search for python tutorials") is True

    def test_accepts_google_phrase(self, tool):
        assert tool.can_handle("google best pizza in lucknow") is True

    def test_rejects_plain_app_name(self, tool):
        # Must NOT claim "open notepad" -- that belongs to OSTool.
        assert tool.can_handle("open notepad") is False

    def test_rejects_bare_search(self, tool):
        # Regression: bare "search X" (no "for") used to collide with
        # SearchTool's trigger, causing a browser to open when the
        # user actually wanted a grounded answer instead.
        assert tool.can_handle("search who is the president") is False

    def test_rejects_bare_look_up(self, tool):
        assert tool.can_handle("look up nasdaq today") is False

    def test_rejects_unrelated_message(self, tool):
        assert tool.can_handle("hello there") is False


class TestExecute:

    def test_open_domain_normalizes_scheme(self, tool):
        with patch("tools.web.tool.webbrowser.open", return_value=True) as mock_open:
            result = tool.execute("open reddit.com")

        assert result.success is True
        mock_open.assert_called_once_with("https://reddit.com")

    def test_open_full_url_is_preserved(self, tool):
        with patch("tools.web.tool.webbrowser.open", return_value=True) as mock_open:
            result = tool.execute("go to https://example.com/page")

        assert result.success is True
        mock_open.assert_called_once_with("https://example.com/page")

    def test_search_query_builds_google_search_url(self, tool):
        with patch("tools.web.tool.webbrowser.open", return_value=True) as mock_open:
            result = tool.execute("search for best pizza")

        assert result.success is True
        called_url = mock_open.call_args[0][0]
        assert "google.com/search" in called_url
        assert "best+pizza" in called_url or "best%20pizza" in called_url

    def test_browser_unavailable_reports_failure(self, tool):
        with patch("tools.web.tool.webbrowser.open", return_value=False):
            result = tool.execute("open google.com")

        assert result.success is False
        assert result.error

    def test_browser_exception_reports_failure(self, tool):
        with patch(
            "tools.web.tool.webbrowser.open", side_effect=OSError("boom")
        ):
            result = tool.execute("open google.com")

        assert result.success is False
        assert "boom" in result.error