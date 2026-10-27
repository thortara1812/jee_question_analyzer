"""Arithmetic subset for numerical substitutions in all three subjects."""
import ast
import math
import operator


def calculate(expression: str) -> float:
    """Evaluate at most 80 arithmetic nodes with bounded numbers and exponents."""
    if not isinstance(expression, str) or not 1 <= len(expression) <= 300:
        raise ValueError("Expression must contain 1–300 characters.")
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, RecursionError) as exc:
        raise ValueError("Invalid arithmetic expression.") from exc
    if len(list(ast.walk(tree))) > 80:
        raise ValueError("Expression is too complex.")

    def bounded(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Only real numbers are supported.")
        if not math.isfinite(value) or abs(value) > 1e100:
            raise ValueError("Number is outside supported bounds.")
        return value

    def visit(node):
        if isinstance(node, ast.Constant):
            return bounded(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return bounded(visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1))
        if isinstance(node, ast.BinOp):
            left, right = visit(node.left), visit(node.right)
            operations = {ast.Add: operator.add, ast.Sub: operator.sub,
                          ast.Mult: operator.mul, ast.Div: operator.truediv,
                          ast.Pow: operator.pow}
            if type(node.op) not in operations:
                raise ValueError("Unsupported operator.")
            if isinstance(node.op, ast.Pow) and abs(right) > 20:
                raise ValueError("Exponent must be between -20 and 20.")
            return bounded(operations[type(node.op)](left, right))
        raise ValueError("Only numbers, parentheses and + - * / ** are allowed.")

    try:
        return float(visit(tree.body))
    except (ArithmeticError, TypeError) as exc:
        raise ValueError("Arithmetic result is undefined or outside bounds.") from exc


def make_calculator(audit: list[dict]):
    """Construct a real CrewAI tool and capture calls for this request only."""
    from crewai.tools import tool

    @tool("bounded_calculator")
    def calculator(expression: str) -> str:
        """Calculate real arithmetic with +, -, *, /, ** and parentheses; include numeric substitutions only."""
        try:
            value = calculate(expression)
            audit.append({"tool": "calculator", "expression": expression,
                          "success": True, "value": value})
            return str(value)
        except ValueError as exc:
            audit.append({"tool": "calculator", "success": False})
            return f"Invalid calculation: {exc}"

    return calculator
