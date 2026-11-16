from __future__ import annotations

import json
from importlib import resources

from sipl.parser import build_ast, parse_tree
from sipl.visualization.tree import (
    GraphvizNotFoundError,
    ViewNode,
    dot_to_svg,
    to_dict,
    to_dot,
    to_text,
)
from sipl.visualization.views import ast_view, parse_tree_view

__all__ = [
    "GraphvizNotFoundError",
    "ViewNode",
    "ast_view",
    "comparison_html",
    "dot_to_svg",
    "parse_tree_view",
    "to_dict",
    "to_dot",
    "to_text",
]


def comparison_html(source: str, title: str = "SIPL program") -> str:
    """Standalone HTML page showing the source, its parse tree and its AST side by side."""
    tree = parse_tree(source)
    payload = {
        "title": title,
        "source": source,
        "parseTree": to_dict(parse_tree_view(tree)),
        "ast": to_dict(ast_view(build_ast(tree))),
    }
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    template = resources.files("sipl").joinpath("visualization", "template.html")
    return template.read_text("utf-8").replace("/*DATA*/", data)
