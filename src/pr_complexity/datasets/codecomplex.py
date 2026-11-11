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

import json
from collections.abc import Iterable
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


@dataclass(frozen=True)
class Program:
    id: int  # 0-based row in the file; `problem` is not unique
    src: str
    label: str  # one of LABELS.values()
    problem: str  # Codeforces problem, e.g. "0005_D"
    tags: tuple[str, ...]  # Codeforces tags, e.g. ("dp", "greedy")


def load_codecomplex(path: str | Path = DEFAULT_PATH) -> list[Program]:
    programs = []
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            raw = row["complexity"]
            if raw not in LABELS:
                raise ValueError(f"{path}:{line_no}: unknown complexity label {raw!r}")
            programs.append(Program(
                id=len(programs),
                src=row["src"],
                label=LABELS[raw],
                problem=row["problem"],
                tags=tuple(t.strip() for t in row["tags"].split(",") if t.strip()),
            ))
    return programs


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
