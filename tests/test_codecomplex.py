import json
from pathlib import Path

import pytest

from pr_complexity.analysis import COMPLEXITY_CLASSES
from pr_complexity.datasets.codecomplex import (
    DEFAULT_PATH,
    LABELS,
    TEST_FRACTION,
    assign_splits,
    dataset_stats,
    load_codecomplex,
    select,
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
    assert [p.has_functions for p in programs] == [False, True]
    assert programs[0].split == programs[1].split  # same problem, same side


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


# 100 problems of 1-9 programs; each problem has one main label and some have
# a second, as in CodeComplex.
SPLIT_ROWS = [
    (f"p{i:03}", "abcd"[i % 4] if j % 5 else "abcd"[(i + j) % 4])
    for i in range(100)
    for j in range(1 + i % 9)
]


def test_split_keeps_problems_together_and_is_deterministic():
    splits = assign_splits(SPLIT_ROWS)
    assert set(splits) == {p for p, _ in SPLIT_ROWS}
    assert set(splits.values()) == {"dev", "test"}
    assert assign_splits(reversed(SPLIT_ROWS)) == splits


def test_split_balances_labels():
    splits = assign_splits(SPLIT_ROWS)
    for label in "abcd":
        rows = [p for p, lab in SPLIT_ROWS if lab == label]
        in_test = sum(splits[p] == "test" for p in rows)
        assert abs(in_test - TEST_FRACTION * len(rows)) <= 3, label


def test_select(tmp_path):
    programs = load_codecomplex(write_jsonl(tmp_path / "d.jsonl", ROWS))
    assert select(programs, "all") == programs
    assert select(programs, "dev") + select(programs, "test") == programs
    with pytest.raises(ValueError):
        select(programs, "train")


@pytest.mark.dataset
@pytest.mark.skipif(not DATA.exists(), reason="run scripts/fetch_codecomplex.py first")
def test_split_of_the_pinned_data():
    programs = load_codecomplex(DATA)
    dev, test = select(programs, "dev"), select(programs, "test")
    # Pinned so a change to the split (which would change the test set) is noticed.
    assert (len(dev), len(test)) == (3895, 1005)
    assert (len({p.problem for p in dev}), len({p.problem for p in test})) == (216, 61)
    assert not {p.problem for p in dev} & {p.problem for p in test}

    def share(programs, label):
        return sum(p.label == label for p in programs) / len(programs)

    for label in LABELS.values():
        assert abs(share(dev, label) - share(test, label)) < 0.01, label
        for fn in (False, True):  # within each reported group too
            d = [p for p in dev if p.has_functions == fn]
            t = [p for p in test if p.has_functions == fn]
            assert abs(share(d, label) - share(t, label)) < 0.03, (label, fn)


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
