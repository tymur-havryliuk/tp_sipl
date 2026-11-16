from __future__ import annotations

import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from sipl.cli import main

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
EXAMPLES = ROOT / "examples"


@dataclass
class CliResult:
    code: int
    out: str
    err: str

    def json(self) -> Any:
        return json.loads(self.out)


@pytest.fixture
def invoke() -> Any:
    def invoke(*argv: str) -> CliResult:
        out, err = io.StringIO(), io.StringIO()
        code = main(list(argv), out=out, err=err)
        return CliResult(code, out.getvalue(), err.getvalue())

    return invoke


@pytest.fixture
def write_source(tmp_path: Path) -> Any:
    def write(text: str, name: str = "program.sipl") -> str:
        path = tmp_path / name
        path.write_text(text, "utf-8")
        return str(path)

    return write
