"""
Tests for CalculatorTool and SafeEvaluator.

Includes a regression test for the exponentiation-based computational
DoS found during Sprint 4 hardening: can_handle()'s regex allows "**",
so an unbounded exponent could previously hang the whole assistant.
"""

import pytest

from tools.calculator.tool import CalculatorTool


@pytest.fixture
def tool():
    return CalculatorTool()


class TestCanHandle:

    def test_accepts_simple_expression(self, tool):
        assert tool.can_handle("2 + 2") is True

    def test_accepts_decimal_expression(self, tool):
        assert tool.can_handle("3.14 * 2") is True

    def test_accepts_expression_with_parentheses(self, tool):
        assert tool.can_handle("(2 + 3) * 4") is True

    def test_rejects_natural_language(self, tool):
        assert tool.can_handle("what is 2 plus 2") is False

    def test_rejects_empty_string(self, tool):
        assert tool.can_handle("") is False

    def test_rejects_whitespace_only(self, tool):
        assert tool.can_handle("   ") is False


class TestExecute:

    def test_addition(self, tool):
        result = tool.execute("2 + 2")
        assert result.success is True
        assert result.data == 4

    def test_division(self, tool):
        result = tool.execute("10 / 4")
        assert result.success is True
        assert result.data == 2.5

    def test_division_by_zero_fails_gracefully(self, tool):
        result = tool.execute("5 / 0")
        assert result.success is False
        assert result.error

    def test_modulo_by_zero_fails_gracefully(self, tool):
        result = tool.execute("5 % 0")
        assert result.success is False

    def test_malformed_expression_fails_gracefully(self, tool):
        # Note: "2 + + + 2" is NOT malformed -- chained unary '+' is
        # valid Python (2 + (+(+2)) == 4). Use a genuine syntax error.
        result = tool.execute("2 + * 3")
        assert result.success is False

    def test_exponent_within_limit(self, tool):
        result = tool.execute("2 ** 10")
        assert result.success is True
        assert result.data == 1024

    def test_exponent_over_limit_is_rejected(self, tool):
        result = tool.execute("9 ** 99999")
        assert result.success is False
        assert "too large" in result.error.lower()

    def test_chained_exponent_dos_is_rejected(self, tool):
        # Regression test: this must fail fast, not hang computing a
        # number with tens of millions of digits.
        result = tool.execute("9**9**9")
        assert result.success is False
        assert "too large" in result.error.lower()