"""The Python part of the CodeComplex dataset.

4,900 Codeforces solutions, each labelled with its worst-case time
complexity. Source: github.com/sybaik1/CodeComplex-Data, file
``python_data.jsonl``, pinned below. The repository states no licence, so
the file is downloaded by ``scripts/fetch_codecomplex.py`` into the
git-ignored ``data/`` directory and never committed.

Every program does its work at the top level, and 2,983 define no function
at all, so each program is analysed as a wrapped module
(:func:`~pr_complexity.graphs.wrap_module`) plus its own functions.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Hashable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from ..graphs import GraphBuildError, build_graph, has_module_code, split_functions, wrap_module

COMMIT = "c54631de24c0c3b0e180e876a9f244fb0905cf86"  # 27 December 2024
URL = f"https://raw.githubusercontent.com/sybaik1/CodeComplex-Data/{COMMIT}/python_data.jsonl"
SHA256 = "0cf4923ad68e57a42392b4f4787476fed9392d182c886f4aec73cd70175e1c3b"
DEFAULT_PATH = Path("data/codecomplex/python_data.jsonl")

# Dataset label -> our complexity class (see analysis.COMPLEXITY_CLASSES).
LABELS = {
    "constant": "O(1)",
    "logn": "O(log n)",
    "linear": "O(n)",
    "nlogn": "O(n log n)",
    "quadratic": "O(n^2)",
    "cubic": "O(n^3)",
    "np": "exponential",  # the dataset's README calls this class "exponential"
}


SPLITS = ("dev", "test")
TEST_FRACTION = 0.2
SPLIT_SEED = "codecomplex-split-v1"  # changing it changes the test set


@dataclass(frozen=True)
class Program:
    id: int  # 0-based row in the file; `problem` is not unique
    src: str
    label: str  # one of LABELS.values()
    problem: str  # Codeforces problem, e.g. "0005_D"
    tags: tuple[str, ...]  # Codeforces tags, e.g. ("dp", "greedy")
    has_functions: bool  # defines at least one function (reported separately)
    split: str  # "dev" (develop and tune on this) or "test" (final results only)


def load_codecomplex(path: str | Path = DEFAULT_PATH) -> list[Program]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if row["complexity"] not in LABELS:
                raise ValueError(
                    f"{path}:{line_no}: unknown complexity label {row['complexity']!r}")
            row["has_functions"] = bool(split_functions(row["src"]))
            rows.append(row)

    splits = assign_splits((row["problem"], (row["complexity"], row["has_functions"]))
                           for row in rows)
    return [
        Program(
            id=i,
            src=row["src"],
            label=LABELS[row["complexity"]],
            problem=row["problem"],
            tags=tuple(t.strip() for t in row["tags"].split(",") if t.strip()),
            has_functions=row["has_functions"],
            split=splits[row["problem"]],
        )
        for i, row in enumerate(rows)
    ]


def assign_splits(rows: Iterable[tuple[str, Hashable]]) -> dict[str, str]:
    """Map each problem to "dev" or "test", given (problem, stratum) pairs.

    The loader's stratum is (label, has_functions), so each label's share
    matches between dev and test both overall and within the two groups
    that are reported separately.

    Every program of a problem goes to the same side: 235 of the 277
    problems have a single label, so a split by row would let the test set
    share problems with the data the analysis was tuned on.

    Problems are visited in a fixed pseudo-random order (SHA-256 of
    SPLIT_SEED and the problem) and moved into or out of the test set
    whenever that brings every stratum's test count closer to TEST_FRACTION
    of its programs, until no move helps. A simple random split would leave
    labels unbalanced, because O(log n), O(n^3) and exponential programs
    come from few, large problems.
    """
    per_problem: dict[str, Counter] = defaultdict(Counter)
    for problem, stratum in rows:
        per_problem[problem][stratum] += 1
    totals = sum(per_problem.values(), Counter())
    target = {stratum: TEST_FRACTION * n for stratum, n in totals.items()}

    def error(counts: Counter) -> float:
        return sum((counts[stratum] - t) ** 2 for stratum, t in target.items())

    order = sorted(per_problem,
                   key=lambda p: hashlib.sha256(f"{SPLIT_SEED}:{p}".encode()).hexdigest())
    test: set[str] = set()
    in_test: Counter = Counter()
    changed = True
    while changed:  # terminates: every move strictly lowers the error
        changed = False
        for p in order:
            moved = in_test - per_problem[p] if p in test else in_test + per_problem[p]
            if error(moved) < error(in_test):
                test ^= {p}
                in_test = moved
                changed = True
    return {p: "test" if p in test else "dev" for p in per_problem}


def select(programs: Iterable[Program], split: str) -> list[Program]:
    """Programs in ``split`` ("dev", "test" or "all")."""
    if split == "all":
        return list(programs)
    if split not in SPLITS:
        raise ValueError(f"unknown split {split!r}")
    return [p for p in programs if p.split == split]


# --------------------------------------------------------------------------
# Statistics for the evaluation section
# --------------------------------------------------------------------------


@dataclass
class LabelStats:
    programs: int = 0
    no_functions: int = 0
    with_functions: int = 0
    failed: int = 0  # programs where the module graph or a function graph failed


@dataclass
class DatasetStats:
    by_label: dict[str, LabelStats] = field(default_factory=dict)
    module_code: int = 0  # programs with code outside functions (need wrapping)
    functions: int = 0  # functions found by split_functions
    module_failures: list[tuple[int, str]] = field(default_factory=list)  # (id, error)
    function_failures: list[tuple[int, str, str]] = field(default_factory=list)  # (id, fn, error)

    @property
    def total(self) -> LabelStats:
        t = LabelStats()
        for s in self.by_label.values():
            t.programs += s.programs
            t.no_functions += s.no_functions
            t.with_functions += s.with_functions
            t.failed += s.failed
        return t


def dataset_stats(programs: Iterable[Program]) -> DatasetStats:
    """Build every module and function graph and count what worked."""
    stats = DatasetStats(by_label={label: LabelStats() for label in LABELS.values()})
    for p in programs:
        s = stats.by_label[p.label]
        s.programs += 1
        functions = split_functions(p.src)
        if functions:
            s.with_functions += 1
        else:
            s.no_functions += 1
        stats.module_code += has_module_code(p.src)
        stats.functions += len(functions)

        failed = False
        try:
            build_graph(wrap_module(p.src))
        except GraphBuildError as exc:
            stats.module_failures.append((p.id, str(exc)))
            failed = True
        for fn in functions:
            try:
                build_graph(fn.source)
            except GraphBuildError as exc:
                stats.function_failures.append((p.id, fn.name, str(exc)))
                failed = True
        s.failed += failed
    return stats
