"""Source text -> Lark parse tree -> typed AST."""

from __future__ import annotations

from functools import cache
from importlib import resources

from lark import Lark, Token, Tree
from lark.exceptions import UnexpectedCharacters, UnexpectedInput, UnexpectedToken

from sipl import ast
from sipl.diagnostics import Diagnostic, SiplSyntaxError

_ARITH_OPS = {
    "+": ast.ArithOp.ADD,
    "-": ast.ArithOp.SUB,
    "*": ast.ArithOp.MUL,
    "/": ast.ArithOp.DIV,
    "÷": ast.ArithOp.DIV,
}

_REL_OPS = {
    "=": ast.RelOp.EQ,
    "!=": ast.RelOp.NE,
    "<>": ast.RelOp.NE,
    "≠": ast.RelOp.NE,
    "<": ast.RelOp.LT,
    "<=": ast.RelOp.LE,
    "≤": ast.RelOp.LE,
    ">": ast.RelOp.GT,
    ">=": ast.RelOp.GE,
    "≥": ast.RelOp.GE,
}

_TERMINAL_NAMES = {
    "VAR": "variable",
    "NUMBER": "number",
    "ADD_OP": "arithmetic operator",
    "MUL_OP": "arithmetic operator",
    "REL_OP": "comparison operator",
    "$END": "end of input",
}

ParseTree = Tree[Token]


@cache
def _lark() -> Lark:
    grammar = resources.files("sipl").joinpath("grammar", "sipl.lark").read_text("utf-8")
    # The basic lexer keeps keywords reserved everywhere; the contextual one would
    # lex `end` in `begin end` as a variable.
    return Lark(
        grammar,
        start="program",
        parser="lalr",
        lexer="basic",
        propagate_positions=True,
        keep_all_tokens=True,
    )


def parse_tree(source: str) -> ParseTree:
    """Concrete syntax tree, including every token of the source."""
    try:
        return _lark().parse(source)
    except UnexpectedInput as error:
        raise SiplSyntaxError(_diagnostic(source, error)) from None


def parse(source: str) -> ast.Program:
    return build_ast(parse_tree(source))


def check(source: str) -> list[Diagnostic]:
    try:
        parse(source)
    except SiplSyntaxError as error:
        return [error.diagnostic]
    return []


def build_ast(tree: ParseTree) -> ast.Program:
    return ast.Program(_stmt(_subtrees(tree)[0]), span=_tree_span(tree))


# Parse tree -> AST


def _subtrees(tree: ParseTree) -> list[ParseTree]:
    return [child for child in tree.children if isinstance(child, Tree)]


def _tree_span(tree: ParseTree) -> ast.SourceSpan:
    m = tree.meta
    return ast.SourceSpan(m.line, m.column, m.end_line, m.end_column, m.start_pos, m.end_pos)


def token_span(token: Token) -> ast.SourceSpan:
    assert token.line is not None and token.column is not None
    assert token.end_line is not None and token.end_column is not None
    assert token.start_pos is not None and token.end_pos is not None
    return ast.SourceSpan(
        token.line, token.column, token.end_line, token.end_column, token.start_pos, token.end_pos
    )


def _stmt(tree: ParseTree) -> ast.Stmt:
    span = _tree_span(tree)
    kids = tree.children
    match tree.data:
        case "stmt":
            statements = tuple(_stmt(child) for child in _subtrees(tree))
            return statements[0] if len(statements) == 1 else ast.Seq(statements, span=span)
        case "assign":
            target, _, value = kids
            assert isinstance(target, Token) and isinstance(value, Tree)
            return ast.Assign(str(target), _aexpr(value), span=span)
        case "if_stmt":
            cond, then_branch, else_branch = _subtrees(tree)
            return ast.If(_bexpr(cond), _stmt(then_branch), _stmt(else_branch), span=span)
        case "while_stmt":
            cond, body = _subtrees(tree)
            return ast.While(_bexpr(cond), _stmt(body), span=span)
        case "block":
            (body,) = _subtrees(tree)
            return ast.Block(_stmt(body), span=span)
        case "skip":
            return ast.Skip(span=span)
    raise AssertionError(f"unexpected statement node {tree.data!r}")


def _aexpr(tree: ParseTree) -> ast.ArithExpr:
    kids = tree.children
    if tree.data in ("aexpr", "term"):
        if len(kids) == 1:
            assert isinstance(kids[0], Tree)
            return _aexpr(kids[0])
        left, op, right = kids
        assert isinstance(left, Tree) and isinstance(right, Tree)
        return ast.BinOp(_ARITH_OPS[str(op)], _aexpr(left), _aexpr(right), span=_tree_span(tree))
    if tree.data == "factor":
        if len(kids) == 3:
            inner = kids[1]
            assert isinstance(inner, Tree)
            return _aexpr(inner)
        (token,) = kids
        assert isinstance(token, Token)
        if token.type == "NUMBER":
            return ast.Num(int(token), span=token_span(token))
        return ast.Var(str(token), span=token_span(token))
    raise AssertionError(f"unexpected arithmetic node {tree.data!r}")


def _bexpr(tree: ParseTree) -> ast.BoolExpr:
    kids = tree.children
    span = _tree_span(tree)
    match tree.data, len(kids):
        case (("bexpr" | "bterm" | "bfactor"), 1):
            assert isinstance(kids[0], Tree)
            return _bexpr(kids[0])
        case ("bexpr" | "bterm") as rule, 3:
            left, _, right = _subtrees(tree)
            op = ast.LogicOp.OR if rule == "bexpr" else ast.LogicOp.AND
            return ast.Logic(op, _bexpr(left), _bexpr(right), span=span)
        case "bfactor", 2:
            return ast.Not(_bexpr(_subtrees(tree)[1]), span=span)
        case "batom", 1:
            return ast.BoolLit(str(kids[0]) == "true", span=span)
        case "batom", 3 if isinstance(kids[1], Token) and kids[1].type == "REL_OP":
            left, right = _subtrees(tree)
            return ast.Compare(_REL_OPS[str(kids[1])], _aexpr(left), _aexpr(right), span=span)
        case "batom", 3:
            assert isinstance(kids[1], Tree)
            return _bexpr(kids[1])
    raise AssertionError(f"unexpected boolean node {tree.data!r}")


# Syntax errors


def _diagnostic(source: str, error: UnexpectedInput) -> Diagnostic:
    if isinstance(error, UnexpectedCharacters):
        offset = error.pos_in_stream
        assert offset is not None
        span = ast.SourceSpan(
            error.line, error.column, error.line, error.column + 1, offset, offset + 1
        )
        char = source[offset] if offset < len(source) else ""
        return Diagnostic("unexpected-character", f"unexpected character {char!r}", span)

    if isinstance(error, UnexpectedToken):
        token = error.token
        expected = _describe_expected(error.accepts or error.expected)
        if token.type == "$END":
            span = _end_span(source)
            return Diagnostic(
                "unexpected-end", f"unexpected end of input, expected {expected}", span
            )
        found = _TERMINAL_NAMES.get(token.type) or ("keyword" if token.isalpha() else "symbol")
        message = f"unexpected {found} {str(token)!r}, expected {expected}"
        return Diagnostic("unexpected-token", message, token_span(token))

    span = _end_span(source)
    return Diagnostic("syntax-error", str(error), span)


def _describe_expected(names: set[str]) -> str:
    descriptions = set()
    for name in names:
        if name in _TERMINAL_NAMES:
            descriptions.add(_TERMINAL_NAMES[name])
            continue
        pattern = _lark().get_terminal(name).pattern
        descriptions.add(repr(pattern.value) if pattern.type == "str" else name.lower())
    ordered = sorted(descriptions)
    return ordered[0] if len(ordered) == 1 else ", ".join(ordered[:-1]) + " or " + ordered[-1]


def _end_span(source: str) -> ast.SourceSpan:
    """Position right after the last non-blank character."""
    end = len(source.rstrip())
    line = source.count("\n", 0, end) + 1
    column = end - (source.rfind("\n", 0, end) + 1) + 1
    return ast.SourceSpan(line, column, line, column, end, end)
