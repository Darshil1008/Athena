"""
Tests for DateTimeTool.

Includes regression tests for the substring-matching false-positive
bug found during Sprint 4 hardening: "day" as a raw substring matched
inside "birthday", "Monday", etc., hijacking unrelated messages.
"""

import pytest

from tools.datetime.tool import DateTimeTool


@pytest.fixture
def tool():
    return DateTimeTool()


class TestCanHandle:

    def test_accepts_time_query(self, tool):
        assert tool.can_handle("what time is it") is True

    def test_accepts_date_query(self, tool):
        assert tool.can_handle("what's the date today") is True

    def test_accepts_weekday_query(self, tool):
        assert tool.can_handle("what day is it") is True

    def test_rejects_unrelated_message(self, tool):
        assert tool.can_handle("hello there") is False

    def test_does_not_false_positive_on_birthday(self, tool):
        # Regression: "day" used to match as a raw substring of
        # "birthday", hijacking this into a date response.
        assert tool.can_handle(
            "it's my birthday, any gift ideas?"
        ) is False

    def test_does_not_false_positive_on_weekday_name(self, tool):
        # Regression: "day" used to match inside "Monday".
        assert tool.can_handle("let's meet on Monday") is False

    def test_does_not_false_positive_on_yesterday(self, tool):
        assert tool.can_handle("I was tired yesterday") is False

    def test_still_matches_today_as_whole_word(self, tool):
        assert tool.can_handle("remind me today") is True


class TestExecute:

    def test_time_query_returns_time_only(self, tool):
        result = tool.execute("what time is it")
        assert result.success is True
        assert ":" in result.data
        assert "\n" not in result.data

    def test_date_query_returns_date_only(self, tool):
        result = tool.execute("what's the date")
        assert result.success is True
        assert "\n" not in result.data

    def test_weekday_query_returns_day_name_only(self, tool):
        result = tool.execute("what day is it")
        assert result.success is True
        assert "\n" not in result.data

    def test_generic_datetime_query_returns_full_summary(self, tool):
        result = tool.execute("tell me the datetime info")
        assert result.success is True
        assert "Date" in result.data
        assert "Time" in result.data
        assert "Day" in result.data