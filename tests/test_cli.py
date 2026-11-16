import io
import subprocess
import sys
from pathlib import Path

import pytest

from sipl import cli

from .conftest import EXAMPLES

POWER = str(EXAMPLES / "power.sipl")


def test_check_ok(invoke) -> None:
    result = invoke("check", POWER)
    assert result.code == cli.EXIT_OK
    assert result.out.strip().endswith(": ok")


def test_check_syntax_error_text(invoke, write_source) -> None:
    path = write_source("begin\n  X := 1\n  Y := 2\nend\n")
    result = invoke("check", path)
    assert result.code == cli.EXIT_SYNTAX_ERROR
    assert f"{path}:3:3: error: unexpected variable 'Y'" in result.err
    assert "3 |   Y := 2" in result.err


def test_check_syntax_error_json(invoke, write_source) -> None:
    result = invoke("check", "--json", write_source("X := "))
    assert result.code == cli.EXIT_SYNTAX_ERROR
    document = result.json()
    assert document["schema_version"] == 1
    assert document["command"] == "check"
    assert document["ok"] is False
    [diagnostic] = document["diagnostics"]
    assert diagnostic["code"] == "unexpected-end"
    assert diagnostic["severity"] == "error"
    assert diagnostic["span"]["start"] == {"line": 1, "column": 5, "offset": 4}


def test_check_json_ok(invoke) -> None:
    assert invoke("check", "--json", POWER).json() == {
        "schema_version": 1,
        "command": "check",
        "ok": True,
        "diagnostics": [],
    }


def test_parse_json(invoke, write_source) -> None:
    document = invoke("parse", "--format", "json", write_source("X := 1 + Y")).json()
    assert document["ok"] is True
    ast = document["ast"]
    assert ast["type"] == "Program"
    assign = ast["body"]
    assert assign["type"] == "Assign" and assign["target"] == "X"
    assert assign["value"]["op"] == "+"
    assert assign["value"]["right"] == {
        "type": "Var",
        "name": "Y",
        "span": {
            "start": {"line": 1, "column": 10, "offset": 9},
            "end": {"line": 1, "column": 11, "offset": 10},
        },
    }


def test_parse_text(invoke) -> None:
    result = invoke("parse", POWER)
    assert result.code == 0
    assert result.out.splitlines()[0] == "Program  @1:1-8:4"
    assert "While  @3:3-7:6" in result.out


def test_tree_text_and_dot(invoke, write_source) -> None:
    path = write_source("skip")
    assert "skip  @1:1-1:5" in invoke("tree", path).out
    dot = invoke("tree", "--format", "dot", path).out
    assert dot.startswith("digraph parse_tree {")
    assert "label=\"'skip'\"" in dot


def test_tree_json(invoke, write_source) -> None:
    tree = invoke("tree", "--format", "json", write_source("skip")).json()["tree"]
    assert tree["label"] == "program"
    leaf = tree["children"][0]["children"][0]["children"][0]
    assert leaf["token"] is True


def test_svg_without_graphviz(invoke, monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _: None)
    result = invoke("parse", "--format", "svg", POWER)
    assert result.code == cli.EXIT_ENVIRONMENT
    assert "Graphviz" in result.err


def test_view_writes_html(invoke, tmp_path: Path) -> None:
    output = tmp_path / "out.html"
    result = invoke("view", POWER, "-o", str(output))
    assert result.code == 0
    assert output.read_text("utf-8").startswith("<!doctype html>")
    assert invoke("view", POWER).out.startswith("<!doctype html>")


def test_run_text(invoke) -> None:
    result = invoke("run", POWER, "-s", "X=3", "--set", "Y=4")
    assert result.code == 0
    assert result.out.splitlines() == ["X = 3", "Y = 0", "R = 81"]


def test_run_json(invoke) -> None:
    document = invoke("run", POWER, "-s", "X=-2", "-s", "Y=3", "--json").json()
    assert document == {
        "schema_version": 1,
        "command": "run",
        "ok": True,
        "state": {"X": -2, "Y": 0, "R": -8},
        "steps": 16,
    }


def test_run_runtime_error(invoke, write_source) -> None:
    path = write_source("X := Y")
    result = invoke("run", path)
    assert result.code == cli.EXIT_RUNTIME_ERROR
    assert "variable 'Y' is not defined [undefined-variable]" in result.err
    document = invoke("run", path, "--json").json()
    assert document["ok"] is False
    assert document["diagnostics"][0]["code"] == "undefined-variable"


def test_run_step_limit(invoke) -> None:
    result = invoke("run", str(EXAMPLES / "infinite.sipl"), "--max-steps", "100")
    assert result.code == cli.EXIT_RUNTIME_ERROR
    assert "step limit of 100 exceeded" in result.err


def test_run_syntax_error(invoke, write_source) -> None:
    assert invoke("run", write_source("X :=")).code == cli.EXIT_SYNTAX_ERROR


def test_trace_text(invoke) -> None:
    result = invoke("trace", str(EXAMPLES / "gcd.sipl"), "-s", "A=6", "-s", "B=4")
    lines = result.out.splitlines()
    assert result.code == 0
    assert lines[0].split() == ["1", "1:1", "while", "A", "!=", "B", "do"]
    assert "A: 6 -> 2" in result.out
    assert "A != B is false" in result.out
    assert lines[-1] == "finished after 5 steps: A = 2, B = 2"


def test_trace_json(invoke, write_source) -> None:
    document = invoke(
        "trace", write_source("X := 1; if X > 0 then skip else skip"), "--json"
    ).json()
    assert document["ok"] is True
    kinds = [event["event"] for event in document["events"]]
    assert kinds[0] == "statement_started" and kinds[-1] == "execution_finished"
    changed = next(e for e in document["events"] if e["event"] == "variable_changed")
    assert changed == {
        "event": "variable_changed",
        "name": "X",
        "old": None,
        "new": 1,
        "span": changed["span"],
    }
    condition = next(e for e in document["events"] if e["event"] == "condition_evaluated")
    assert condition["statement"] == "If" and condition["value"] is True
    assert condition["span"]["start"]["column"] == 12


def test_trace_runtime_error(invoke, write_source) -> None:
    path = write_source("X := 1;\nX := X / 0")
    result = invoke("trace", path, "--json")
    assert result.code == cli.EXIT_RUNTIME_ERROR
    document = result.json()
    assert document["ok"] is False
    assert document["diagnostics"][0]["code"] == "division-by-zero"
    assert any(e["event"] == "variable_changed" for e in document["events"])
    text = invoke("trace", path)
    assert "X: ⊥ -> 1" in text.out
    assert "division by zero" in text.err


def test_stdin(invoke, monkeypatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("X := 40 + 2"))
    result = invoke("run", "-")
    assert result.out == "X = 42\n"


def test_missing_file(invoke, tmp_path: Path) -> None:
    result = invoke("check", str(tmp_path / "missing.sipl"))
    assert result.code == cli.EXIT_ENVIRONMENT
    assert "cannot read" in result.err


@pytest.mark.parametrize("bad", ["X", "X=", "1X=2", "X=1.5", "X=abc"])
def test_invalid_initial_state(invoke, bad: str) -> None:
    with pytest.raises(SystemExit) as info:
        invoke("run", POWER, "-s", bad)
    assert info.value.code == cli.EXIT_USAGE


def test_console_entry_point_runs_as_module() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "sipl.cli", "--version"], capture_output=True, text=True, check=True
    )
    assert completed.stdout.startswith("sipl ")
