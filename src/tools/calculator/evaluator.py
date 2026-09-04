"""
Safe mathematical expression evaluator for Athena.
"""

import ast
import operator


_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

# Exponents beyond this produce results with enough digits to hang
# the (single-threaded) assistant on a simple arithmetic query -- e.g.
# 9**9**9**9 is a valid match for CalculatorTool.can_handle()'s regex
# but would otherwise compute for an unbounded amount of time.
_MAX_EXPONENT = 1000


class SafeEvaluator:
    """
    Safely evaluates arithmetic expressions using Python's AST.
    """

    def evaluate(self, expression: str):
        tree = ast.parse(expression, mode="eval")
        return self._evaluate_node(tree.body)

    def _evaluate_node(self, node):

        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.BinOp):
            left = self._evaluate_node(node.left)
            right = self._evaluate_node(node.right)

            if isinstance(node.op, ast.Pow) and abs(right) > _MAX_EXPONENT:
                raise ValueError(
                    f"Exponent too large (limit is {_MAX_EXPONENT})."
                )

            operator_func = _OPERATORS[type(node.op)]

            return operator_func(left, right)

        if isinstance(node, ast.UnaryOp):
            operand = self._evaluate_node(node.operand)

            operator_func = _OPERATORS[type(node.op)]

            return operator_func(operand)

        raise ValueError("Unsupported mathematical expression.")