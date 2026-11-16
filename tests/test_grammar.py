"""CORE-01: the grammar accepts the course language and rejects everything else."""

from pathlib import Path

import pytest

from sipl import SiplSyntaxError, parse

from .conftest import EXAMPLES, FIXTURES

VALID = sorted((FIXTURES / "valid").glob("*.sipl")) + sorted(EXAMPLES.glob("*.sipl"))
INVALID = sorted((FIXTURES / "invalid").glob("*.sipl"))


def test_fixture_counts_meet_requirement() -> None:
    assert len(list((FIXTURES / "valid").glob("*.sipl"))) >= 10
    assert len(INVALID) >= 10


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.name)
def test_valid_programs_parse(path: Path) -> None:
    parse(path.read_text("utf-8"))


@pytest.mark.parametrize("path", INVALID, ids=lambda p: p.name)
def test_invalid_programs_are_rejected(path: Path) -> None:
    with pytest.raises(SiplSyntaxError):
        parse(path.read_text("utf-8"))


@pytest.mark.parametrize("source", ["andy := 1", "endless := 1", "skipper := 0", "if_ := 2"])
def test_identifiers_with_keyword_prefix_are_variables(source: str) -> None:
    parse(source)


@pytest.mark.parametrize(
    "keyword",
    [
        "begin",
        "end",
        "if",
        "then",
        "else",
        "while",
        "do",
        "skip",
        "true",
        "false",
        "and",
        "or",
        "not",
    ],
)
def test_keywords_are_reserved(keyword: str) -> None:
    with pytest.raises(SiplSyntaxError):
        parse(f"{keyword} := 1")
