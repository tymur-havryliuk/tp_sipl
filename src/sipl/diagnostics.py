from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from sipl.ast import SourceSpan


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    message: str
    span: SourceSpan
    severity: Severity = Severity.ERROR

    def format(self, filename: str = "<input>") -> str:
        line, column = self.span.start_line, self.span.start_column
        return f"{filename}:{line}:{column}: {self.severity.value}: {self.message} [{self.code}]"

    def render(self, source: str, filename: str = "<input>") -> str:
        """format() plus the offending source line with a caret underline."""
        lines = source.splitlines()
        span = self.span
        if not 1 <= span.start_line <= len(lines):
            return self.format(filename)
        text = lines[span.start_line - 1]
        width = span.end_column - span.start_column if span.end_line == span.start_line else 1
        marker = " " * (span.start_column - 1) + "^" + "~" * max(width - 1, 0)
        gutter = f"{span.start_line} | "
        return "\n".join(
            [self.format(filename), gutter + text, " " * (len(gutter) - 2) + "| " + marker]
        )


class SiplError(Exception):
    def __init__(self, diagnostic: Diagnostic) -> None:
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic

    @property
    def span(self) -> SourceSpan:
        return self.diagnostic.span


class SiplSyntaxError(SiplError):
    pass


class SiplRuntimeError(SiplError):
    pass


class StepLimitExceeded(SiplRuntimeError):
    pass
