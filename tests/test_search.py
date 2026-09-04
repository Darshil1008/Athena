"""
Tests for SearchTool.

Network calls (urllib.request.urlopen) are mocked throughout -- these
tests must never make a real HTTP request.
"""

from unittest.mock import MagicMock, patch

import pytest

from tools.search.tool import SearchTool


@pytest.fixture
def tool():
    return SearchTool()


_SAMPLE_HTML = """
<div class="result">
  <a rel="nofollow" class="result__a" href="https://example.com/a">
    Example Result <b>One</b>
  </a>
  <a class="result__snippet">This is the first snippet.</a>
</div>
<div class="result">
  <a rel="nofollow" class="result__a" href="https://example.com/b">
    Example Result Two
  </a>
  <a class="result__snippet">This is the second snippet.</a>
</div>
"""


def _mock_response(html: str):
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value.read.return_value = html.encode("utf-8")
    return mock_cm


class TestCanHandle:

    def test_accepts_bare_search(self, tool):
        assert tool.can_handle("search who is the pm of india") is True

    def test_accepts_bare_look_up(self, tool):
        assert tool.can_handle("look up nasdaq today") is True

    def test_accepts_bare_ask(self, tool):
        assert tool.can_handle("ask latest news") is True

    def test_colon_form_still_works(self, tool):
        # Colon is optional, not required, after the fix.
        assert tool.can_handle("search: who is the pm") is True

    def test_rejects_plain_conversation(self, tool):
        assert tool.can_handle("Hi") is False

    def test_rejects_search_for_phrasing(self, tool):
        # "search for X" belongs to WebTool (opens a browser), not
        # this tool -- this was the exact collision found in testing.
        assert tool.can_handle("search for python tutorials") is False

    def test_rejects_look_for_phrasing(self, tool):
        assert tool.can_handle("look for my file") is False


class TestExecute:

    def test_successful_search_flags_needs_synthesis(self, tool):
        with patch(
            "tools.search.tool.urllib.request.urlopen",
            return_value=_mock_response(_SAMPLE_HTML),
        ):
            result = tool.execute("search current president of india")

        assert result.success is True
        assert result.data == "current president of india"
        assert result.metadata["needs_synthesis"] is True
        assert "Example Result" in result.metadata["search_results"]
        assert "first snippet" in result.metadata["search_results"]

    def test_empty_query_after_trigger_fails_cleanly(self, tool):
        result = tool.execute("search")
        assert result.success is False

    def test_no_results_found_fails_cleanly(self, tool):
        with patch(
            "tools.search.tool.urllib.request.urlopen",
            return_value=_mock_response("<html>no results here</html>"),
        ):
            result = tool.execute("search asdkjaskldjaskld")

        assert result.success is False
        assert "no search results" in result.error.lower()

    def test_network_failure_fails_cleanly(self, tool):
        import urllib.error

        with patch(
            "tools.search.tool.urllib.request.urlopen",
            side_effect=urllib.error.URLError("no connection"),
        ):
            result = tool.execute("search anything")

        assert result.success is False
        assert "couldn't reach" in result.error.lower()