import json
import re

from sipl import parse, parse_tree
from sipl.visualization import (
    ast_view,
    comparison_html,
    dot_to_svg,
    parse_tree_view,
    to_dict,
    to_dot,
    to_text,
)

SOURCE = "begin\n  X := (1 + Y) * 2;\n  skip\nend"


def test_parse_tree_keeps_every_token_in_order() -> None:
    view = parse_tree_view(parse_tree(SOURCE))
    tokens = [node for node in view.walk() if node.is_leaf_token]
    assert "".join(node.span.text(SOURCE) for node in tokens) == re.sub(r"\s", "", SOURCE)


def test_parse_tree_nodes_cover_their_children() -> None:
    view = parse_tree_view(parse_tree(SOURCE))
    for node in view.walk():
        for child in node.children:
            assert node.span.start_offset <= child.span.start_offset
            assert child.span.end_offset <= node.span.end_offset


def test_parse_tree_has_grammar_rules_and_ast_does_not() -> None:
    parse_labels = {node.label for node in parse_tree_view(parse_tree(SOURCE)).walk()}
    ast_labels = {node.label for node in ast_view(parse(SOURCE)).walk()}
    assert {"program", "stmt", "aexpr", "term", "factor", "'('", "';'"} <= parse_labels
    assert ast_labels == {
        "Program",
        "Block",
        "Seq",
        "Assign X :=",
        "BinOp *",
        "BinOp +",
        "Num 1",
        "Num 2",
        "Var Y",
        "Skip",
    }


def test_ast_view_is_smaller_than_parse_tree() -> None:
    parse_size = sum(1 for _ in parse_tree_view(parse_tree(SOURCE)).walk())
    ast_size = sum(1 for _ in ast_view(parse(SOURCE)).walk())
    assert ast_size < parse_size / 2


def test_ast_labels() -> None:
    view = ast_view(parse("if not true and X <= 1 then skip else skip"))
    labels = [node.label for node in view.walk()]
    assert labels[:6] == ["Program", "If", "Logic and", "Not", "BoolLit true", "Compare <="]


def test_text_rendering() -> None:
    text = to_text(ast_view(parse("X := 1; skip")))
    assert text.splitlines() == [
        "Program  @1:1-1:13",
        "└── Seq  @1:1-1:13",
        "    ├── Assign X :=  @1:1-1:7",
        "    │   └── Num 1  @1:6-1:7",
        "    └── Skip  @1:9-1:13",
    ]


def test_dot_rendering() -> None:
    dot = to_dot(ast_view(parse("X := 1")), "ast")
    assert dot.startswith("digraph ast {")
    assert 'n0 [label="Program", tooltip="1:1-1:7"];' in dot
    assert "n1 -> n2;" in dot
    assert dot.rstrip().endswith("}")


def test_dot_escapes_quotes() -> None:
    dot = to_dot(parse_tree_view(parse_tree("skip")))
    assert "label=\"'skip'\"" in dot


def test_dict_rendering() -> None:
    data = to_dict(ast_view(parse("skip")))
    assert data["label"] == "Program"
    assert data["children"][0] == {
        "label": "Skip",
        "span": {
            "start": {"line": 1, "column": 1, "offset": 0},
            "end": {"line": 1, "column": 5, "offset": 4},
        },
    }


def test_html_embeds_both_trees() -> None:
    html = comparison_html("X := 1", title="t.sipl")
    payload = re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S)
    assert payload is not None
    data = json.loads(payload.group(1))
    assert data["title"] == "t.sipl"
    assert data["parseTree"]["label"] == "program"
    assert data["ast"]["label"] == "Program"


def test_html_escapes_closing_script_tag_in_data() -> None:
    html = comparison_html("X := 1", title="</script><b>")
    assert "</script><b>" not in html


def test_dot_to_svg_uses_graphviz(monkeypatch) -> None:
    calls = []

    class Completed:
        stdout = "<svg/>"

    def fake_run(args, **kwargs):
        calls.append((args, kwargs["input"]))
        return Completed()

    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/dot")
    monkeypatch.setattr("subprocess.run", fake_run)
    assert dot_to_svg("digraph {}") == "<svg/>"
    assert calls == [(["/usr/bin/dot", "-Tsvg"], "digraph {}")]
