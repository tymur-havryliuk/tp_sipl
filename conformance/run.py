#!/usr/bin/env python3
"""Run the SIPL conformance suite against any implementation of the `sipl` CLI contract.

Standard library only, so it can be used without installing this package:

    python conformance/run.py --sipl "sipl"
    python conformance/run.py --sipl "node my-impl/cli.js" conformance/cases
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

EXIT_CODES = {"ok": 0, "syntax_error": 1, "runtime_error": 3}


class CaseFailure(Exception):
    pass


def strip_spans(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: strip_spans(v) for k, v in value.items() if k != "span"}
    if isinstance(value, list):
        return [strip_spans(item) for item in value]
    return value


def invoke(command: list[str], *args: str) -> tuple[int, Any]:
    completed = subprocess.run([*command, *args], capture_output=True, text=True, check=False)
    try:
        document = json.loads(completed.stdout)
    except json.JSONDecodeError:
        raise CaseFailure(
            f"`{shlex.join([*command, *args])}` exited with {completed.returncode} "
            f"and did not print JSON: {completed.stderr.strip()[:200]}"
        ) from None
    return completed.returncode, document


def check_case(command: list[str], source: Path, spec: dict[str, Any]) -> None:
    expect = spec["expect"]
    status = expect["status"]

    if "ast" in expect:
        code, document = invoke(command, "parse", "--format", "json", str(source))
        if code != 0:
            raise CaseFailure(f"parse exited with {code}")
        actual = strip_spans(document["ast"])
        if actual != expect["ast"]:
            raise CaseFailure(f"AST mismatch:\n  expected {expect['ast']}\n  actual   {actual}")

    args = ["run", "--json"]
    for name, value in spec.get("input", {}).items():
        args += ["--set", f"{name}={value}"]
    if "max_steps" in spec:
        args += ["--max-steps", str(spec["max_steps"])]
    code, document = invoke(command, *args, str(source))

    if code != EXIT_CODES[status]:
        raise CaseFailure(f"expected exit code {EXIT_CODES[status]} ({status}), got {code}")
    if document.get("ok") is not (status == "ok"):
        raise CaseFailure(f"expected ok={status == 'ok'}, got {document.get('ok')}")

    if status == "ok":
        if document["state"] != expect["state"]:
            raise CaseFailure(f"final state {document['state']} != expected {expect['state']}")
        return

    diagnostic = document["diagnostics"][0]
    error = expect["error"]
    if diagnostic["code"] != error["code"]:
        raise CaseFailure(f"error code {diagnostic['code']!r} != expected {error['code']!r}")
    start = diagnostic["span"]["start"]
    for key in ("line", "column"):
        if key in error and start[key] != error[key]:
            raise CaseFailure(f"error {key} {start[key]} != expected {error[key]}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("cases", nargs="?", type=Path, default=Path(__file__).parent / "cases")
    parser.add_argument("--sipl", default="sipl", help="command that runs the implementation")
    parser.add_argument("-q", "--quiet", action="store_true", help="only report failures")
    args = parser.parse_args(argv)

    command = shlex.split(args.sipl)
    specs = sorted(args.cases.glob("*.json"))
    if not specs:
        print(f"no cases found in {args.cases}", file=sys.stderr)
        return 2

    failures = 0
    for spec_path in specs:
        source = spec_path.with_suffix(".sipl")
        try:
            check_case(command, source, json.loads(spec_path.read_text("utf-8")))
        except (CaseFailure, KeyError, OSError) as error:
            failures += 1
            print(f"FAIL {spec_path.stem}: {error}")
        else:
            if not args.quiet:
                print(f"pass {spec_path.stem}")

    print(f"\n{len(specs) - failures}/{len(specs)} cases passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
