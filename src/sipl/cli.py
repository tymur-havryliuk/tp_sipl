"""Command-line interface. JSON output format and exit codes are documented in docs/cli.md."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, TextIO

from sipl import ast, interpreter, visualization
from sipl.diagnostics import SiplError, SiplSyntaxError
from sipl.interpreter import (
    ConditionEvaluated,
    ExecutionFinished,
    StatementStarted,
    VariableChanged,
)
from sipl.parser import parse, parse_tree
from sipl.serialize import SCHEMA_VERSION, ast_to_dict, diagnostic_to_dict, event_to_dict

EXIT_OK = 0
EXIT_SYNTAX_ERROR = 1
EXIT_USAGE = 2
EXIT_RUNTIME_ERROR = 3
EXIT_ENVIRONMENT = 4

_ASSIGNMENT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(-?[0-9]+)$")


class _Context:
    def __init__(self, args: argparse.Namespace, out: TextIO, err: TextIO) -> None:
        self.args = args
        self.out = out
        self.err = err
        self.filename = "<stdin>" if args.file == "-" else args.file
        self.source = ""

    def emit_json(self, ok: bool, **payload: Any) -> None:
        document = {"schema_version": SCHEMA_VERSION, "command": self.args.command, "ok": ok}
        document.update(payload)
        json.dump(document, self.out, ensure_ascii=False, indent=2)
        self.out.write("\n")

    def fail(self, error: SiplError, code: int, **payload: Any) -> int:
        if self.json:
            self.emit_json(False, diagnostics=[diagnostic_to_dict(error.diagnostic)], **payload)
        else:
            print(error.diagnostic.render(self.source, self.filename), file=self.err)
        return code

    @property
    def json(self) -> bool:
        return bool(getattr(self.args, "json", False) or getattr(self.args, "format", "") == "json")


def _initial_state(text: str) -> tuple[str, int]:
    match = _ASSIGNMENT.match(text)
    if match is None:
        raise argparse.ArgumentTypeError(f"expected NAME=INTEGER, got {text!r}")
    return match.group(1), int(match.group(2))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sipl", description="SIPL language toolkit")
    parser.add_argument("--version", action="version", version=f"%(prog)s {_version()}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    def command(name: str, help_text: str) -> argparse.ArgumentParser:
        sub = commands.add_parser(name, help=help_text, description=help_text)
        sub.add_argument("file", metavar="FILE", help="SIPL source file, '-' for stdin")
        return sub

    check = command("check", "check syntax and report diagnostics")
    check.add_argument("--json", action="store_true", help="machine-readable output")

    for name, help_text in (
        ("parse", "print the abstract syntax tree"),
        ("tree", "print the concrete parse tree"),
    ):
        sub = command(name, help_text)
        sub.add_argument("--format", choices=["text", "json", "dot", "svg"], default="text")

    view = command("view", "write an HTML page comparing the parse tree and the AST")
    view.add_argument("-o", "--output", type=Path, help="output file (default: stdout)")

    for name, help_text in (
        ("run", "execute a program and print the final state"),
        ("trace", "execute a program and print every execution event"),
    ):
        sub = command(name, help_text)
        sub.add_argument(
            "-s",
            "--set",
            dest="state",
            action="append",
            type=_initial_state,
            default=[],
            metavar="NAME=VALUE",
            help="initial variable value",
        )
        sub.add_argument(
            "--max-steps",
            type=int,
            default=interpreter.DEFAULT_MAX_STEPS,
            help="abort after this many executed statements (default: %(default)s)",
        )
        sub.add_argument("--json", action="store_true", help="machine-readable output")
    return parser


def main(
    argv: Sequence[str] | None = None, *, out: TextIO | None = None, err: TextIO | None = None
) -> int:
    args = _build_parser().parse_args(argv)
    ctx = _Context(args, out or sys.stdout, err or sys.stderr)
    try:
        ctx.source = sys.stdin.read() if args.file == "-" else Path(args.file).read_text("utf-8")
    except OSError as error:
        print(f"sipl: cannot read {ctx.filename}: {error.strerror}", file=ctx.err)
        return EXIT_ENVIRONMENT

    handler = {
        "check": _check,
        "parse": _parse,
        "tree": _tree,
        "view": _view,
        "run": _run,
        "trace": _trace,
    }[args.command]
    try:
        return handler(ctx)
    except SiplSyntaxError as error:
        return ctx.fail(error, EXIT_SYNTAX_ERROR)
    except visualization.GraphvizNotFoundError as error:
        print(f"sipl: {error}; use --format dot instead", file=ctx.err)
        return EXIT_ENVIRONMENT


def _check(ctx: _Context) -> int:
    parse(ctx.source)
    if ctx.json:
        ctx.emit_json(True, diagnostics=[])
    else:
        print(f"{ctx.filename}: ok", file=ctx.out)
    return EXIT_OK


def _parse(ctx: _Context) -> int:
    program = parse(ctx.source)
    if ctx.args.format == "json":
        ctx.emit_json(True, ast=ast_to_dict(program))
    else:
        _print_tree(ctx, visualization.ast_view(program), "ast")
    return EXIT_OK


def _tree(ctx: _Context) -> int:
    view = visualization.parse_tree_view(parse_tree(ctx.source))
    if ctx.args.format == "json":
        ctx.emit_json(True, tree=visualization.to_dict(view))
    else:
        _print_tree(ctx, view, "parse_tree")
    return EXIT_OK


def _print_tree(ctx: _Context, view: visualization.ViewNode, name: str) -> None:
    fmt = ctx.args.format
    if fmt == "text":
        print(visualization.to_text(view), file=ctx.out)
    elif fmt == "dot":
        ctx.out.write(visualization.to_dot(view, name))
    else:
        ctx.out.write(visualization.dot_to_svg(visualization.to_dot(view, name)))


def _view(ctx: _Context) -> int:
    html = visualization.comparison_html(ctx.source, title=ctx.filename)
    if ctx.args.output is None:
        ctx.out.write(html)
    else:
        ctx.args.output.write_text(html, "utf-8")
        print(f"wrote {ctx.args.output}", file=ctx.err)
    return EXIT_OK


def _run(ctx: _Context) -> int:
    program = parse(ctx.source)
    try:
        result = interpreter.run(program, dict(ctx.args.state), max_steps=ctx.args.max_steps)
    except SiplError as error:
        return ctx.fail(error, EXIT_RUNTIME_ERROR)
    if ctx.json:
        ctx.emit_json(True, state=result.state, steps=result.steps)
    else:
        for name, value in result.state.items():
            print(f"{name} = {value}", file=ctx.out)
    return EXIT_OK


def _trace(ctx: _Context) -> int:
    program = parse(ctx.source)
    trace = interpreter.record(program, dict(ctx.args.state), max_steps=ctx.args.max_steps)
    events = [event_to_dict(event) for event in trace.events]
    if ctx.json:
        diagnostics = [diagnostic_to_dict(trace.error.diagnostic)] if trace.error else []
        ctx.emit_json(trace.error is None, events=events, diagnostics=diagnostics)
    else:
        for event in trace.events:
            line = _describe_event(event, ctx.source)
            if line:
                print(line, file=ctx.out)
        if trace.error:
            print(trace.error.diagnostic.render(ctx.source, ctx.filename), file=ctx.err)
    return EXIT_RUNTIME_ERROR if trace.error else EXIT_OK


def _describe_event(event: interpreter.Event, source: str) -> str | None:
    match event:
        case StatementStarted(statement, step) if not isinstance(statement, ast.Seq):
            text = statement.span.text(source).splitlines()[0]
            return (
                f"{step:>5}  {statement.span.start_line:>3}:{statement.span.start_column:<3} {text}"
            )
        case VariableChanged(_, name, old, new):
            before = "⊥" if old is None else str(old)
            return f"{'':>16}{name}: {before} -> {new}"
        case ConditionEvaluated(statement, value):
            return f"{'':>16}{statement.condition.span.text(source)} is {str(value).lower()}"
        case ExecutionFinished(state, steps):
            values = ", ".join(f"{k} = {v}" for k, v in state.items())
            return f"finished after {steps} steps: {values}"
    return None


def _version() -> str:
    try:
        return version("sipl-toolkit")
    except PackageNotFoundError:
        return "unknown"


if __name__ == "__main__":
    sys.exit(main())
