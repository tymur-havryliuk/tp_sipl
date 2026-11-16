from __future__ import annotations

from collections.abc import Iterator, Mapping
from types import MappingProxyType

from sipl import ast
from sipl.diagnostics import Diagnostic, SiplRuntimeError, StepLimitExceeded
from sipl.interpreter.events import (
    ConditionEvaluated,
    Event,
    ExecutionFinished,
    StatementFinished,
    StatementStarted,
    VariableChanged,
)

DEFAULT_MAX_STEPS = 100_000


def execute(
    program: ast.Program,
    state: Mapping[str, int] | None = None,
    *,
    max_steps: int = DEFAULT_MAX_STEPS,
) -> Iterator[Event]:
    """Run the program lazily, yielding events; the last one is ExecutionFinished.

    Raises SiplRuntimeError when execution is undefined (unbound variable,
    division by zero) and StepLimitExceeded when more than max_steps statements
    were executed.
    """
    return _Machine(dict(state or {}), max_steps).run(program)


class _Machine:
    def __init__(self, state: dict[str, int], max_steps: int) -> None:
        self.state = state
        self.max_steps = max_steps
        self.steps = 0

    def run(self, program: ast.Program) -> Iterator[Event]:
        yield from self.exec(program.body)
        yield ExecutionFinished(MappingProxyType(dict(self.state)), self.steps)

    def exec(self, stmt: ast.Stmt) -> Iterator[Event]:
        self.steps += 1
        if self.steps > self.max_steps:
            raise StepLimitExceeded(
                Diagnostic("step-limit", f"step limit of {self.max_steps} exceeded", stmt.span)
            )
        yield StatementStarted(stmt, self.steps)

        match stmt:
            case ast.Assign(target, value):
                new = self.arith(value)
                old = self.state.get(target)
                self.state[target] = new
                yield VariableChanged(stmt, target, old, new)
            case ast.Seq(statements):
                for child in statements:
                    yield from self.exec(child)
            case ast.Block(body):
                yield from self.exec(body)
            case ast.If(condition, then_branch, else_branch):
                chosen = self.boolean(condition)
                yield ConditionEvaluated(stmt, chosen)
                yield from self.exec(then_branch if chosen else else_branch)
            case ast.While(condition, body):
                while True:
                    holds = self.boolean(condition)
                    yield ConditionEvaluated(stmt, holds)
                    if not holds:
                        break
                    yield from self.exec(body)
            case ast.Skip():
                pass

        yield StatementFinished(stmt)

    def arith(self, expr: ast.ArithExpr) -> int:
        match expr:
            case ast.Num(value):
                return value
            case ast.Var(name):
                if name not in self.state:
                    raise SiplRuntimeError(
                        Diagnostic(
                            "undefined-variable", f"variable '{name}' is not defined", expr.span
                        )
                    )
                return self.state[name]
            case ast.BinOp(op, left, right):
                a, b = self.arith(left), self.arith(right)
                if op is ast.ArithOp.ADD:
                    return a + b
                if op is ast.ArithOp.SUB:
                    return a - b
                if op is ast.ArithOp.MUL:
                    return a * b
                if b == 0:
                    raise SiplRuntimeError(
                        Diagnostic("division-by-zero", "division by zero", expr.span)
                    )
                return _div_toward_zero(a, b)
        raise AssertionError(expr)

    def boolean(self, expr: ast.BoolExpr) -> bool:
        match expr:
            case ast.BoolLit(value):
                return value
            case ast.Compare(op, left, right):
                return _compare(op, self.arith(left), self.arith(right))
            case ast.Not(operand):
                return not self.boolean(operand)
            case ast.Logic(op, left, right):
                # Strict: both operands are evaluated, as in the semantic term.
                a, b = self.boolean(left), self.boolean(right)
                return (a and b) if op is ast.LogicOp.AND else (a or b)
        raise AssertionError(expr)


def _div_toward_zero(a: int, b: int) -> int:
    quotient = abs(a) // abs(b)
    return -quotient if (a < 0) != (b < 0) else quotient


def _compare(op: ast.RelOp, a: int, b: int) -> bool:
    match op:
        case ast.RelOp.EQ:
            return a == b
        case ast.RelOp.NE:
            return a != b
        case ast.RelOp.LT:
            return a < b
        case ast.RelOp.LE:
            return a <= b
        case ast.RelOp.GT:
            return a > b
        case ast.RelOp.GE:
            return a >= b
