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


def test_codecomplex_stats_command(tmp_path, capsys):
    data = tmp_path / "python_data.jsonl"
    data.write_text(
        '{"src": "print(int(input()))\\n", "complexity": "constant", "problem": "0001_A",'
        ' "from": "CODEFORCES", "tags": "math"}\n',
        encoding="utf-8",
    )
    assert main(["codecomplex-stats", "--data", str(data)]) == 0
    out = capsys.readouterr().out
    assert "O(1)" in out and "total" in out
    assert "Module graphs failed: 0 of 1" in out


def test_codecomplex_stats_missing_file(tmp_path, capsys):
    assert main(["codecomplex-stats", "--data", str(tmp_path / "missing.jsonl")]) == 2
    assert "fetch_codecomplex.py" in capsys.readouterr().err
