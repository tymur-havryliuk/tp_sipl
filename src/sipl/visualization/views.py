"""Adapters from parse trees and ASTs to ViewNode."""

from __future__ import annotations

from lark import Token, Tree

from sipl import ast
from sipl.parser import ParseTree, token_span
from sipl.visualization.tree import ViewNode

_NAMED_TERMINALS = {"VAR", "NUMBER", "ADD_OP", "MUL_OP", "REL_OP"}


def parse_tree_view(tree: ParseTree) -> ViewNode:
    children = tuple(
        parse_tree_view(child) if isinstance(child, Tree) else _token_view(child)
        for child in tree.children
    )
    m = tree.meta
    span = ast.SourceSpan(m.line, m.column, m.end_line, m.end_column, m.start_pos, m.end_pos)
    return ViewNode(str(tree.data), span, children)


def _token_view(token: Token) -> ViewNode:
    label = f"{token.type} {token.value}" if token.type in _NAMED_TERMINALS else repr(token.value)
    return ViewNode(label, token_span(token), is_leaf_token=True)


def ast_view(node: ast.Node) -> ViewNode:
    children = tuple(ast_view(child) for child in node.children())
    return ViewNode(_ast_label(node), node.span, children)


def _ast_label(node: ast.Node) -> str:
    name = type(node).__name__
    match node:
        case ast.Num(value):
            return f"{name} {value}"
        case ast.Var(var):
            return f"{name} {var}"
        case ast.BoolLit(value):
            return f"{name} {str(value).lower()}"
        case ast.BinOp(op) | ast.Compare(op) | ast.Logic(op):
            return f"{name} {op.value}"
        case ast.Assign(target):
            return f"{name} {target} :="
    return name
