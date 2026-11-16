import json
import shlex
import subprocess
import sys
from pathlib import Path

from .conftest import ROOT

RUNNER = ROOT / "conformance" / "run.py"
SIPL = shlex.join([sys.executable, "-m", "sipl.cli"])


def run_suite(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RUNNER), "--sipl", SIPL, *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_reference_implementation_passes_suite() -> None:
    completed = run_suite("--quiet")
    assert completed.returncode == 0, completed.stdout
    assert "FAIL" not in completed.stdout


def test_every_case_has_source_and_valid_spec() -> None:
    cases = ROOT / "conformance" / "cases"
    specs = sorted(cases.glob("*.json"))
    assert len(specs) >= 20
    for spec_path in specs:
        assert spec_path.with_suffix(".sipl").exists(), spec_path
        spec = json.loads(spec_path.read_text("utf-8"))
        assert spec["description"]
        assert spec["expect"]["status"] in {"ok", "syntax_error", "runtime_error"}


def test_runner_reports_mismatches(tmp_path: Path) -> None:
    (tmp_path / "wrong.sipl").write_text("X := 2 + 2", "utf-8")
    spec = {"description": "deliberately wrong", "expect": {"status": "ok", "state": {"X": 5}}}
    (tmp_path / "wrong.json").write_text(json.dumps(spec), "utf-8")
    completed = run_suite(str(tmp_path))
    assert completed.returncode == 1
    assert "FAIL wrong: final state {'X': 4} != expected {'X': 5}" in completed.stdout


def test_runner_reports_non_json_output(tmp_path: Path) -> None:
    (tmp_path / "case.sipl").write_text("skip", "utf-8")
    spec = {"description": "d", "expect": {"status": "ok", "state": {}}}
    (tmp_path / "case.json").write_text(json.dumps(spec), "utf-8")
    completed = subprocess.run(
        [sys.executable, str(RUNNER), "--sipl", "echo not-json", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    assert "did not print JSON" in completed.stdout
