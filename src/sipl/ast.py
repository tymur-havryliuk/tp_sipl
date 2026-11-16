"""Typed abstract syntax tree of SIPL.

Nodes are immutable. Source spans do not take part in equality, so two trees
parsed from differently formatted sources compare equal.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class SourceSpan:
    """Half-open source range. Lines and columns are 1-based, offsets 0-based."""

    start_line: int
    start_column: int
    end_line: int
    end_column: int
    start_offset: int
    end_offset: int

    def contains(self, line: int, column: int) -> bool:
        start = (self.start_line, self.start_column)
        end = (self.end_line, self.end_column)
        return start <= (line, column) < end

    def text(self, source: str) -> str:
        return source[self.start_offset : self.end_offset]

    def __str__(self) -> str:
        return f"{self.start_line}:{self.start_column}-{self.end_line}:{self.end_column}"


UNKNOWN_SPAN = SourceSpan(0, 0, 0, 0, 0, 0)


class ArithOp(StrEnum):
    ADD = "+"
    SUB = "-"
    MUL = "*"
    DIV = "/"


class RelOp(StrEnum):
    EQ = "="
    NE = "!="
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="


class LogicOp(StrEnum):
    AND = "and"
    OR = "or"


@dataclass(frozen=True, slots=True)
class Node:
    span: SourceSpan = field(default=UNKNOWN_SPAN, compare=False, repr=False, kw_only=True)

    def children(self) -> Iterator[Node]:
        return iter(())


# Arithmetic expressions


@dataclass(frozen=True, slots=True)
class Num(Node):
    value: int


@dataclass(frozen=True, slots=True)
class Var(Node):
    name: str


@dataclass(frozen=True, slots=True)
class BinOp(Node):
    op: ArithOp
    left: ArithExpr
    right: ArithExpr

    def children(self) -> Iterator[Node]:
        yield self.left
        yield self.right


ArithExpr = Num | Var | BinOp


# Boolean expressions


@dataclass(frozen=True, slots=True)
class BoolLit(Node):
    value: bool


@dataclass(frozen=True, slots=True)
class Compare(Node):
    op: RelOp
    left: ArithExpr
    right: ArithExpr

    def children(self) -> Iterator[Node]:
        yield self.left
        yield self.right


@dataclass(frozen=True, slots=True)
class Not(Node):
    operand: BoolExpr

    def children(self) -> Iterator[Node]:
        yield self.operand


@dataclass(frozen=True, slots=True)
class Logic(Node):
    op: LogicOp
    left: BoolExpr
    right: BoolExpr

    def children(self) -> Iterator[Node]:
        yield self.left
        yield self.right


BoolExpr = BoolLit | Compare | Not | Logic


# Statements


@dataclass(frozen=True, slots=True)
class Assign(Node):
    target: str
    value: ArithExpr

    def children(self) -> Iterator[Node]:
        yield self.value


@dataclass(frozen=True, slots=True)
class Seq(Node):
    statements: tuple[Stmt, ...]

    def children(self) -> Iterator[Node]:
        yield from self.statements


@dataclass(frozen=True, slots=True)
class If(Node):
    condition: BoolExpr
    then_branch: Stmt
    else_branch: Stmt

    def children(self) -> Iterator[Node]:
        yield self.condition
        yield self.then_branch
        yield self.else_branch


@dataclass(frozen=True, slots=True)
class While(Node):
    condition: BoolExpr
    body: Stmt

    def children(self) -> Iterator[Node]:
        yield self.condition
        yield self.body


@dataclass(frozen=True, slots=True)
class Block(Node):
    body: Stmt

    def children(self) -> Iterator[Node]:
        yield self.body


@dataclass(frozen=True, slots=True)
class Skip(Node):
    pass


Stmt = Assign | Seq | If | While | Block | Skip


@dataclass(frozen=True, slots=True)
class Program(Node):
    body: Stmt

    def children(self) -> Iterator[Node]:
        yield self.body


def walk(node: Node) -> Iterator[Node]:
    """Pre-order traversal."""
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(reversed(list(current.children())))
