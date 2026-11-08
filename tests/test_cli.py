from pathlib import Path

from pr_complexity.cli import main

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "single" / "nested_loops.py"


def test_functions_command(capsys):
    assert main(["functions", str(EXAMPLE)]) == 0
    assert "count_equal_pairs" in capsys.readouterr().out


def test_graph_command_writes_dot(tmp_path, capsys):
    out = tmp_path / "g.dot"
    assert main(["graph", str(EXAMPLE), "--dot", str(out), "--no-syntax"]) == 0
    assert out.read_text().startswith("digraph")
    assert "control-flow" in capsys.readouterr().out


def test_unknown_function(capsys):
    assert main(["graph", str(EXAMPLE), "--function", "missing"]) == 2
