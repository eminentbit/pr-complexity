import json
from pathlib import Path

import pytest

from pr_complexity.analysis import COMPLEXITY_CLASSES
from pr_complexity.datasets.codecomplex import (
    DEFAULT_PATH,
    LABELS,
    dataset_stats,
    load_codecomplex,
)

DATA = Path(__file__).resolve().parent.parent / DEFAULT_PATH

ROWS = [
    {"src": "n = int(input())\nfor i in range(n):\n    print(i)\n",
     "complexity": "linear", "problem": "0001_A", "from": "CODEFORCES", "tags": "implementation"},
    {"src": "def f(n):\n    return 2 ** n\nprint(f(int(input())))\n",
     "complexity": "np", "problem": "0001_A", "from": "CODEFORCES", "tags": "dp,greedy"},
]


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def test_labels_map_to_complexity_classes():
    assert set(LABELS.values()) <= set(COMPLEXITY_CLASSES)


def test_load(tmp_path):
    programs = load_codecomplex(write_jsonl(tmp_path / "d.jsonl", ROWS))
    assert [p.id for p in programs] == [0, 1]  # same problem, different ids
    assert [p.label for p in programs] == ["O(n)", "exponential"]
    assert programs[1].tags == ("dp", "greedy")
    assert programs[0].problem == "0001_A"


def test_unknown_label(tmp_path):
    path = write_jsonl(tmp_path / "d.jsonl", [{**ROWS[0], "complexity": "quartic"}])
    with pytest.raises(ValueError, match="quartic"):
        load_codecomplex(path)


def test_stats(tmp_path):
    stats = dataset_stats(load_codecomplex(write_jsonl(tmp_path / "d.jsonl", ROWS)))
    assert stats.by_label["O(n)"].no_functions == 1
    assert stats.by_label["exponential"].with_functions == 1
    assert (stats.total.programs, stats.total.failed) == (2, 0)
    assert (stats.module_code, stats.functions) == (2, 1)


@pytest.mark.dataset
@pytest.mark.skipif(not DATA.exists(), reason="run scripts/fetch_codecomplex.py first")
def test_whole_dataset_builds():
    programs = load_codecomplex(DATA)
    assert len(programs) == 4900
    stats = dataset_stats(programs)
    assert stats.module_failures == []
    assert stats.function_failures == []
    assert stats.module_code == 4900
    assert (stats.total.no_functions, stats.total.with_functions) == (2983, 1917)
