"""Observable execution events. The interpreter yields them in program order."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from sipl import ast


@dataclass(frozen=True, slots=True)
class StatementStarted:
    statement: ast.Stmt
    step: int


@dataclass(frozen=True, slots=True)
class StatementFinished:
    statement: ast.Stmt


@dataclass(frozen=True, slots=True)
class VariableChanged:
    statement: ast.Assign
    name: str
    old: int | None
    new: int


@dataclass(frozen=True, slots=True)
class ConditionEvaluated:
    statement: ast.If | ast.While
    value: bool


@dataclass(frozen=True, slots=True)
class ExecutionFinished:
    state: Mapping[str, int]
    steps: int


Event = (
    StatementStarted | StatementFinished | VariableChanged | ConditionEvaluated | ExecutionFinished
)
