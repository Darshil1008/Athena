"""
Tests for FileTool.

DEFAULT_SEARCH_ROOTS is monkeypatched to a pytest tmp_path for every
test, so these never touch the real Desktop/Documents/Downloads.
"""

from pathlib import Path

import pytest

from tools.files import tool as file_tool_module
from tools.files.tool import FileTool


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """
    Point FileTool's search roots at an isolated temp directory and
    return it, pre-populated with a couple of files.
    """

    root = tmp_path / "Documents"
    root.mkdir()

    (root / "report.txt").write_text("quarterly numbers go here", encoding="utf-8")
    (root / "report_final.txt").write_text("final version", encoding="utf-8")
    (root / "photo.png").write_bytes(b"\x89PNG\r\n\x1a\nnotrealpngdata")

    monkeypatch.setattr(file_tool_module, "DEFAULT_SEARCH_ROOTS", [root])

    return root


@pytest.fixture
def tool():
    return FileTool()


class TestCanHandle:

    def test_accepts_find_file_query(self, tool):
        assert tool.can_handle("find file report.txt") is True

    def test_accepts_read_file_query(self, tool):
        assert tool.can_handle("read file report.txt") is True

    def test_rejects_query_without_file_keyword(self, tool):
        assert tool.can_handle("find my keys") is False

    def test_rejects_unrelated_message(self, tool):
        assert tool.can_handle("hello there") is False


class TestFind:

    def test_finds_single_exact_match(self, tool, sandbox):
        result = tool.execute("find file report_final.txt")
        assert result.success is True
        assert "report_final.txt" in result.data

    def test_finds_multiple_partial_matches(self, tool, sandbox):
        result = tool.execute("find file report")
        assert result.success is True
        assert "report.txt" in result.data
        assert "report_final.txt" in result.data

    def test_no_match_fails_cleanly(self, tool, sandbox):
        result = tool.execute("find file doesnotexist.txt")
        assert result.success is False


class TestRead:

    def test_reads_file_by_exact_name(self, tool, sandbox):
        result = tool.execute("read file report_final.txt")
        assert result.success is True
        assert result.data == "final version"

    def test_reads_file_by_full_path(self, tool, sandbox):
        full_path = sandbox / "report.txt"
        result = tool.execute(f"read file {full_path}")
        assert result.success is True
        assert result.data == "quarterly numbers go here"

    def test_binary_file_is_rejected(self, tool, sandbox):
        result = tool.execute("read file photo.png")
        assert result.success is False
        assert "text file" in result.error.lower()

    def test_ambiguous_name_asks_to_be_more_specific(self, tool, sandbox):
        result = tool.execute("read file report")
        assert result.success is False
        assert "multiple" in result.error.lower()

    def test_missing_file_fails_cleanly(self, tool, sandbox):
        result = tool.execute("read file nope.txt")
        assert result.success is False

    def test_large_file_is_truncated(self, tool, sandbox):
        big_file = sandbox / "big.txt"
        big_file.write_text("x" * 300_000, encoding="utf-8")

        result = tool.execute("read file big.txt")

        assert result.success is True
        assert "truncated" in result.data
        assert len(result.data) < 300_000