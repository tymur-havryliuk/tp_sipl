"""Renderer-neutral tree used for both the parse tree and the AST."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from sipl.ast import SourceSpan
from sipl.serialize import span_to_dict


@dataclass(frozen=True, slots=True)
class ViewNode:
    label: str
    span: SourceSpan
    children: tuple[ViewNode, ...] = ()
    is_leaf_token: bool = False

    def walk(self) -> Iterator[ViewNode]:
        yield self
        for child in self.children:
            yield from child.walk()


def to_dict(node: ViewNode) -> dict[str, Any]:
    result: dict[str, Any] = {"label": node.label, "span": span_to_dict(node.span)}
    if node.is_leaf_token:
        result["token"] = True
    if node.children:
        result["children"] = [to_dict(child) for child in node.children]
    return result


def to_text(node: ViewNode) -> str:
    lines: list[str] = []

    def visit(current: ViewNode, prefix: str, connector: str, child_prefix: str) -> None:
        lines.append(f"{prefix}{connector}{current.label}  @{current.span}")
        for i, child in enumerate(current.children):
            last = i == len(current.children) - 1
            visit(
                child, prefix + child_prefix, "└── " if last else "├── ", "    " if last else "│   "
            )

    visit(node, "", "", "")
    return "\n".join(lines)


def to_dot(node: ViewNode, name: str = "tree") -> str:
    lines = [f"digraph {name} {{", '  node [shape=box, fontname="Helvetica", fontsize=11];']
    ids: dict[int, str] = {}

    for index, current in enumerate(node.walk()):
        ids[id(current)] = f"n{index}"
        style = ', style=filled, fillcolor="#eef3ff"' if current.is_leaf_token else ""
        label = _dot_escape(current.label)
        tooltip = _dot_escape(str(current.span))
        lines.append(f'  n{index} [label="{label}", tooltip="{tooltip}"{style}];')

    for current in node.walk():
        for child in current.children:
            lines.append(f"  {ids[id(current)]} -> {ids[id(child)]};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _dot_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


class GraphvizNotFoundError(RuntimeError):
    pass


def dot_to_svg(dot: str) -> str:
    executable = shutil.which("dot")
    if executable is None:
        raise GraphvizNotFoundError("Graphviz 'dot' executable not found in PATH")
    completed = subprocess.run(
        [executable, "-Tsvg"], input=dot, capture_output=True, text=True, check=True
    )
    return completed.stdout
