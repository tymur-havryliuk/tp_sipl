from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from sipl import ast
from sipl.diagnostics import SiplRuntimeError
from sipl.interpreter.events import (
    ConditionEvaluated,
    Event,
    ExecutionFinished,
    StatementFinished,
    StatementStarted,
    VariableChanged,
)
from sipl.interpreter.machine import DEFAULT_MAX_STEPS, execute

__all__ = [
    "DEFAULT_MAX_STEPS",
    "ConditionEvaluated",
    "Event",
    "ExecutionFinished",
    "ExecutionResult",
    "StatementFinished",
    "StatementStarted",
    "Trace",
    "VariableChanged",
    "execute",
    "record",
    "run",
]


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    state: dict[str, int]
    steps: int


def run(
    program: ast.Program,
    state: Mapping[str, int] | None = None,
    *,
    max_steps: int = DEFAULT_MAX_STEPS,
    on_event: Callable[[Event], None] | None = None,
) -> ExecutionResult:
    for event in execute(program, state, max_steps=max_steps):
        if on_event is not None:
            on_event(event)
        if isinstance(event, ExecutionFinished):
            return ExecutionResult(dict(event.state), event.steps)
    raise AssertionError("execution ended without ExecutionFinished")


@dataclass(slots=True)
class Trace:
    """Events of one run. On a runtime error, holds the events up to the failure."""

    events: list[Event] = field(default_factory=list)
    error: SiplRuntimeError | None = None

    @property
    def result(self) -> ExecutionResult | None:
        last = self.events[-1] if self.events else None
        if isinstance(last, ExecutionFinished):
            return ExecutionResult(dict(last.state), last.steps)
        return None


def record(
    program: ast.Program,
    state: Mapping[str, int] | None = None,
    *,
    max_steps: int = DEFAULT_MAX_STEPS,
) -> Trace:
    trace = Trace()
    try:
        trace.events.extend(execute(program, state, max_steps=max_steps))
    except SiplRuntimeError as error:
        trace.error = error
    return trace
