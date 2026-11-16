import pytest

from sipl import SiplRuntimeError, parse, record, run
from sipl.diagnostics import StepLimitExceeded
from sipl.interpreter import (
    ConditionEvaluated,
    ExecutionFinished,
    StatementFinished,
    StatementStarted,
    VariableChanged,
    execute,
)

from .conftest import EXAMPLES


def run_file(name: str, **state: int) -> dict[str, int]:
    return run(parse((EXAMPLES / name).read_text("utf-8")), state).state


def evaluate(expression: str, **state: int) -> int:
    return run(parse(f"RESULT := {expression}"), state).state["RESULT"]


def holds(condition: str, **state: int) -> bool:
    return run(parse(f"if {condition} then R := 1 else R := 0"), state).state["R"] == 1


@pytest.mark.parametrize(
    ("x", "y", "expected"), [(2, 10, 1024), (5, 0, 1), (0, 3, 0), (-3, 3, -27)]
)
def test_power(x: int, y: int, expected: int) -> None:
    assert run_file("power.sipl", X=x, Y=y)["R"] == expected


@pytest.mark.parametrize(("n", "expected"), [(0, 1), (1, 1), (5, 120), (10, 3628800)])
def test_factorial(n: int, expected: int) -> None:
    assert run_file("factorial.sipl", N=n)["F"] == expected


@pytest.mark.parametrize(("a", "b", "expected"), [(84, 36, 12), (7, 7, 7), (17, 5, 1)])
def test_gcd(a: int, b: int, expected: int) -> None:
    assert run_file("gcd.sipl", A=a, B=b) == {"A": expected, "B": expected}


def test_fibonacci() -> None:
    assert run_file("fibonacci.sipl", N=10)["A"] == 55


@pytest.mark.parametrize(("a", "b", "c", "expected"), [(1, 2, 3, 3), (3, 2, 1, 3), (2, 3, 1, 3)])
def test_max3(a: int, b: int, c: int, expected: int) -> None:
    assert run_file("max3.sipl", A=a, B=b, C=c)["M"] == expected


def test_arithmetic() -> None:
    assert evaluate("2 + 3 * 4") == 14
    assert evaluate("(2 + 3) * 4") == 20
    assert evaluate("10 - 3 - 2") == 5
    assert evaluate("X * X - 1", X=7) == 48
    assert evaluate("2 * 1000000000000 * 1000000000000") == 2 * 10**24


@pytest.mark.parametrize(
    ("a", "b", "q"), [(7, 2, 3), (-7, 2, -3), (7, -2, -3), (-7, -2, 3), (0, 5, 0)]
)
def test_division_truncates_toward_zero(a: int, b: int, q: int) -> None:
    assert evaluate("A / B", A=a, B=b) == q


def test_divmod_invariant() -> None:
    for x in range(-10, 11):
        for y in (-3, -1, 1, 4):
            state = run_file("divmod.sipl", X=x, Y=y)
            assert state["Q"] * y + state["R"] == x


def test_comparisons() -> None:
    assert holds("1 < 2") and holds("2 <= 2") and holds("3 > 2") and holds("2 >= 2")
    assert holds("2 = 2") and holds("1 != 2")
    assert not holds("2 < 2") and not holds("1 = 2")


def test_logic() -> None:
    assert holds("true and not false")
    assert holds("false or true")
    assert not holds("true and false")
    assert not holds("not (true or false)")


def test_logic_is_strict() -> None:
    with pytest.raises(SiplRuntimeError) as info:
        run(parse("if true or UNKNOWN > 0 then skip else skip"))
    assert info.value.diagnostic.code == "undefined-variable"


def test_while_with_false_condition_does_not_execute_body() -> None:
    assert run(parse("while false do X := 1")).state == {}


def test_initial_state_is_not_mutated() -> None:
    state = {"X": 1}
    result = run(parse("X := X + 1; Y := 0"), state)
    assert state == {"X": 1}
    assert result.state == {"X": 2, "Y": 0}


def test_undefined_variable() -> None:
    source = "X := 1;\nY := X + Z"
    with pytest.raises(SiplRuntimeError) as info:
        run(parse(source))
    diagnostic = info.value.diagnostic
    assert diagnostic.code == "undefined-variable"
    assert "'Z'" in diagnostic.message
    assert info.value.span.text(source) == "Z"


def test_division_by_zero() -> None:
    source = "X := 10 / (Y - Y)"
    with pytest.raises(SiplRuntimeError) as info:
        run(parse(source), {"Y": 3})
    assert info.value.diagnostic.code == "division-by-zero"
    assert info.value.span.text(source) == "10 / (Y - Y)"


def test_step_limit_stops_infinite_loop() -> None:
    with pytest.raises(StepLimitExceeded) as info:
        run(parse((EXAMPLES / "infinite.sipl").read_text("utf-8")), max_steps=500)
    assert info.value.diagnostic.code == "step-limit"


def test_step_limit_is_inclusive() -> None:
    program = parse("skip; skip")
    assert run(program, max_steps=3).steps == 3
    with pytest.raises(StepLimitExceeded):
        run(program, max_steps=2)


def test_event_sequence() -> None:
    program = parse("X := 1; while X < 2 do X := X + 1")
    kinds = [(type(e).__name__, getattr(e, "value", None)) for e in execute(program)]
    assert kinds == [
        ("StatementStarted", None),  # Seq
        ("StatementStarted", None),  # X := 1
        ("VariableChanged", None),
        ("StatementFinished", None),
        ("StatementStarted", None),  # while
        ("ConditionEvaluated", True),
        ("StatementStarted", None),  # X := X + 1
        ("VariableChanged", None),
        ("StatementFinished", None),
        ("ConditionEvaluated", False),
        ("StatementFinished", None),  # while
        ("StatementFinished", None),  # Seq
        ("ExecutionFinished", None),
    ]


def test_variable_changed_reports_old_and_new_value() -> None:
    events = [e for e in execute(parse("X := 1; X := X * 5")) if isinstance(e, VariableChanged)]
    assert [(e.name, e.old, e.new) for e in events] == [("X", None, 1), ("X", 1, 5)]


def test_statement_events_are_balanced() -> None:
    depth = 0
    for event in execute(parse((EXAMPLES / "gcd.sipl").read_text("utf-8")), {"A": 9, "B": 6}):
        if isinstance(event, StatementStarted):
            depth += 1
        elif isinstance(event, StatementFinished):
            depth -= 1
        assert depth >= 0
    assert depth == 0


def test_execution_is_lazy() -> None:
    events = execute(parse("while true do skip"), max_steps=10**9)
    first = [next(events) for _ in range(5)]
    assert isinstance(first[1], ConditionEvaluated)


def test_run_reports_events_to_listener() -> None:
    seen: list[object] = []
    result = run(parse("X := 1"), on_event=seen.append)
    assert isinstance(seen[-1], ExecutionFinished)
    assert result.steps == 1


def test_record_keeps_events_before_failure() -> None:
    trace = record(parse("X := 1; Y := X / 0; Z := 2"))
    assert trace.error is not None
    assert trace.result is None
    changes = [e for e in trace.events if isinstance(e, VariableChanged)]
    assert [c.name for c in changes] == ["X"]


def test_record_success() -> None:
    trace = record(parse("X := 2"))
    assert trace.error is None
    assert trace.result is not None and trace.result.state == {"X": 2}
