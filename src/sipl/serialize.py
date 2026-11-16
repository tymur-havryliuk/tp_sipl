"""JSON-compatible representations of AST, diagnostics and execution events.

This is the public contract of `sipl ... --json`; see docs/cli.md.
"""

from __future__ import annotations

import dataclasses
from enum import Enum
from typing import Any

from sipl import ast
from sipl.diagnostics import Diagnostic
from sipl.interpreter import (
    ConditionEvaluated,
    Event,
    ExecutionFinished,
    StatementFinished,
    StatementStarted,
    VariableChanged,
)

SCHEMA_VERSION = 1

JSON = dict[str, Any]


def span_to_dict(span: ast.SourceSpan) -> JSON:
    return {
        "start": {
            "line": span.start_line,
            "column": span.start_column,
            "offset": span.start_offset,
        },
        "end": {"line": span.end_line, "column": span.end_column, "offset": span.end_offset},
    }


def ast_to_dict(node: ast.Node, *, spans: bool = True) -> JSON:
    result: JSON = {"type": type(node).__name__}
    for f in dataclasses.fields(node):
        if f.name != "span":
            result[f.name] = _value(getattr(node, f.name), spans)
    if spans:
        result["span"] = span_to_dict(node.span)
    return result


def _value(value: Any, spans: bool) -> Any:
    if isinstance(value, ast.Node):
        return ast_to_dict(value, spans=spans)
    if isinstance(value, tuple):
        return [_value(item, spans) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value


def diagnostic_to_dict(diagnostic: Diagnostic) -> JSON:
    return {
        "severity": diagnostic.severity.value,
        "code": diagnostic.code,
        "message": diagnostic.message,
        "span": span_to_dict(diagnostic.span),
    }


def event_to_dict(event: Event) -> JSON:
    match event:
        case StatementStarted(statement, step):
            return {
                "event": "statement_started",
                "statement": type(statement).__name__,
                "step": step,
                "span": span_to_dict(statement.span),
            }
        case StatementFinished(statement):
            return {
                "event": "statement_finished",
                "statement": type(statement).__name__,
                "span": span_to_dict(statement.span),
            }
        case VariableChanged(statement, name, old, new):
            return {
                "event": "variable_changed",
                "name": name,
                "old": old,
                "new": new,
                "span": span_to_dict(statement.span),
            }
        case ConditionEvaluated(statement, value):
            return {
                "event": "condition_evaluated",
                "statement": type(statement).__name__,
                "value": value,
                "span": span_to_dict(statement.condition.span),
            }
        case ExecutionFinished(state, steps):
            return {"event": "execution_finished", "state": dict(state), "steps": steps}
    raise AssertionError(event)
