import pytest

from sipl import SiplSyntaxError, parse
from sipl.ast import (
    ArithOp,
    Assign,
    BinOp,
    Block,
    BoolLit,
    Compare,
    If,
    Logic,
    LogicOp,
    Not,
    Num,
    Program,
    RelOp,
    Seq,
    Skip,
    SourceSpan,
    Var,
    While,
    walk,
)
from sipl.parser import check


def body(source: str):
    return parse(source).body


def value(source: str):
    stmt = body(f"X := {source}")
    assert isinstance(stmt, Assign)
    return stmt.value


def condition(source: str):
    stmt = body(f"while {source} do skip")
    assert isinstance(stmt, While)
    return stmt.condition


def test_power_program() -> None:
    program = parse("""
        begin
          R := 1;
          while Y > 0 do
          begin
            R := R * X;
            Y := Y - 1
          end
        end""")
    expected = Program(
        Block(
            Seq(
                (
                    Assign("R", Num(1)),
                    While(
                        Compare(RelOp.GT, Var("Y"), Num(0)),
                        Block(
                            Seq(
                                (
                                    Assign("R", BinOp(ArithOp.MUL, Var("R"), Var("X"))),
                                    Assign("Y", BinOp(ArithOp.SUB, Var("Y"), Num(1))),
                                )
                            )
                        ),
                    ),
                )
            )
        )
    )
    assert program == expected


def test_single_statement_is_not_wrapped_in_seq() -> None:
    assert body("skip") == Skip()


def test_sequence_is_flat() -> None:
    assert body("skip; skip; skip") == Seq((Skip(), Skip(), Skip()))


def test_if_branches_are_single_statements() -> None:
    assert body("if true then X := 1 else begin X := 2; Y := 3 end") == If(
        BoolLit(True),
        Assign("X", Num(1)),
        Block(Seq((Assign("X", Num(2)), Assign("Y", Num(3))))),
    )


def test_while_body_ends_at_semicolon() -> None:
    stmt = body("while X > 0 do X := X - 1; Y := 0")
    assert isinstance(stmt, Seq)
    assert isinstance(stmt.statements[0], While)
    assert stmt.statements[1] == Assign("Y", Num(0))


def test_multiplication_binds_tighter_than_addition() -> None:
    assert value("1 + 2 * 3") == BinOp(ArithOp.ADD, Num(1), BinOp(ArithOp.MUL, Num(2), Num(3)))


def test_arithmetic_is_left_associative() -> None:
    assert value("10 - 3 - 2") == BinOp(ArithOp.SUB, BinOp(ArithOp.SUB, Num(10), Num(3)), Num(2))
    assert value("8 / 4 / 2") == BinOp(ArithOp.DIV, BinOp(ArithOp.DIV, Num(8), Num(4)), Num(2))


def test_parentheses_override_precedence() -> None:
    assert value("(1 + 2) * 3") == BinOp(ArithOp.MUL, BinOp(ArithOp.ADD, Num(1), Num(2)), Num(3))


def test_boolean_precedence_not_and_or() -> None:
    a = Compare(RelOp.EQ, Var("A"), Num(1))
    b = Compare(RelOp.EQ, Var("B"), Num(1))
    c = Compare(RelOp.EQ, Var("C"), Num(1))
    assert condition("not A = 1 or B = 1 and C = 1") == Logic(
        LogicOp.OR, Not(a), Logic(LogicOp.AND, b, c)
    )


def test_parenthesized_condition_and_arithmetic_are_distinguished() -> None:
    assert condition("(X + 1) > 2") == Compare(
        RelOp.GT, BinOp(ArithOp.ADD, Var("X"), Num(1)), Num(2)
    )
    assert condition("(X > 2)") == Compare(RelOp.GT, Var("X"), Num(2))


@pytest.mark.parametrize(
    ("text", "op"),
    [
        ("=", RelOp.EQ),
        ("!=", RelOp.NE),
        ("<>", RelOp.NE),
        ("≠", RelOp.NE),
        ("<", RelOp.LT),
        ("<=", RelOp.LE),
        ("≤", RelOp.LE),
        (">", RelOp.GT),
        (">=", RelOp.GE),
        ("≥", RelOp.GE),
    ],
)
def test_relational_operator_spellings(text: str, op: RelOp) -> None:
    assert condition(f"X {text} 1") == Compare(op, Var("X"), Num(1))


@pytest.mark.parametrize(
    ("and_", "or_", "not_"),
    [
        ("and", "or", "not"),
        ("&", "|", "!"),
        ("∧", "∨", "¬"),
    ],
)
def test_logical_operator_spellings(and_: str, or_: str, not_: str) -> None:
    assert condition(f"{not_} true {and_} false {or_} true") == Logic(
        LogicOp.OR, Logic(LogicOp.AND, Not(BoolLit(True)), BoolLit(False)), BoolLit(True)
    )


def test_division_spellings() -> None:
    assert value("6 ÷ 3") == value("6 / 3") == BinOp(ArithOp.DIV, Num(6), Num(3))


def test_spans_point_into_source() -> None:
    source = "begin\n  R := 1;\n  R := R * 2\nend"
    program = parse(source)
    assign = next(
        node for node in walk(program) if isinstance(node, Assign) and isinstance(node.value, BinOp)
    )
    assert assign.span == SourceSpan(3, 3, 3, 13, 18, 28)
    assert assign.span.text(source) == "R := R * 2"
    assert assign.value.span.text(source) == "R * 2"
    assert program.span.text(source) == source


def test_every_node_has_a_span() -> None:
    program = parse("if (X + 1) > 2 and not false then X := (1) else skip")
    for node in walk(program):
        assert node.span.end_offset > node.span.start_offset, node


def test_parenthesized_expression_span_excludes_parentheses() -> None:
    source = "X := (1 + 2)"
    stmt = parse(source).body
    assert isinstance(stmt, Assign)
    assert stmt.value.span.text(source) == "1 + 2"


def test_span_contains() -> None:
    span = SourceSpan(2, 3, 2, 8, 0, 0)
    assert span.contains(2, 3) and span.contains(2, 7)
    assert not span.contains(2, 8) and not span.contains(1, 5)
    assert str(span) == "2:3-2:8"


def test_equality_ignores_formatting() -> None:
    assert parse("X:=1;Y:=X+2") == parse("X := 1;\n\n   Y := X + 2")


@pytest.mark.parametrize(
    ("source", "code", "line", "column", "fragment"),
    [
        ("X := 1\nY := 2", "unexpected-token", 2, 1, "unexpected variable 'Y'"),
        ("begin X := 1\n\n", "unexpected-end", 1, 13, "expected 'end'"),
        ("X := 1 # 2", "unexpected-character", 1, 8, "unexpected character '#'"),
        ("if X > 0 then skip", "unexpected-end", 1, 19, "expected 'else'"),
        ("begin end", "unexpected-token", 1, 7, "unexpected keyword 'end'"),
        ("X = 1", "unexpected-token", 1, 3, "expected ':='"),
    ],
)
def test_syntax_diagnostics(source: str, code: str, line: int, column: int, fragment: str) -> None:
    with pytest.raises(SiplSyntaxError) as info:
        parse(source)
    diagnostic = info.value.diagnostic
    assert (diagnostic.code, diagnostic.span.start_line, diagnostic.span.start_column) == (
        code,
        line,
        column,
    )
    assert fragment in diagnostic.message


def test_check_returns_diagnostics_instead_of_raising() -> None:
    assert check("skip") == []
    [diagnostic] = check("skip skip")
    assert diagnostic.format("a.sipl").startswith("a.sipl:1:6: error: unexpected keyword")


def test_render_shows_source_line_with_caret() -> None:
    [diagnostic] = check("begin\n  X := 1 +\nend")
    assert diagnostic.render("begin\n  X := 1 +\nend", "p.sipl").splitlines() == [
        "p.sipl:3:1: error: unexpected keyword 'end', expected '(', number or variable "
        "[unexpected-token]",
        "3 | end",
        "  | ^~~",
    ]
