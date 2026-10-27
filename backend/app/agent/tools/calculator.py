"""Read-only arithmetic tool.

Uses ``ast`` so the agent cannot execute arbitrary Python. Only numeric constants and
``+ - * / // % **`` and unary plus/minus are accepted.
"""

import ast
import operator
from typing import Any

_BINOPS: dict[type, Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY: dict[type, Any] = {ast.UAdd: operator.pos, ast.USub: operator.neg}

MAX_EXPRESSION_CHARS = 80


class CalculatorError(ValueError):
    """The expression is empty, too long, or not safe arithmetic."""


def _eval(node: ast.AST) -> float:
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, int | float)
        and not isinstance(node.value, bool)
    ):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return float(_UNARY[type(node.op)](_eval(node.operand)))
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        left = _eval(node.left)
        right = _eval(node.right)
        if isinstance(node.op, ast.Pow) and (abs(left) > 1e6 or abs(right) > 12):
            raise CalculatorError("Exponentiation is limited to keep results bounded.")
        try:
            return float(_BINOPS[type(node.op)](left, right))
        except ZeroDivisionError as exc:
            raise CalculatorError("Division by zero.") from exc
    raise CalculatorError("Only numbers and + - * / // % ** are allowed.")


def calculate(expression: str) -> str:
    expr = (expression or "").strip().replace(",", "")
    if not expr:
        raise CalculatorError("An expression is required, e.g. '12 * (3 + 4)'.")
    if len(expr) > MAX_EXPRESSION_CHARS:
        raise CalculatorError(f"Expression is longer than {MAX_EXPRESSION_CHARS} characters.")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise CalculatorError("Could not parse the expression.") from exc
    value = _eval(tree.body)
    if value.is_integer():
        return str(int(value))
    return f"{value:.10g}"
