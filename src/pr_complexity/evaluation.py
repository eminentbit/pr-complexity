"""Scoring complexity predictions against labelled programs.

A prediction of "unknown" counts as wrong for accuracy; coverage says how
often the analysis gave an answer at all. Results are also averaged per
problem, because CodeComplex problems range from 1 to 138 programs and a few
large ones would otherwise dominate.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from .analysis import COMPLEXITY_CLASSES, estimate_complexity
from .datasets.codecomplex import Program
from .graphs import GraphBuildError, build_graph, wrap_module

UNKNOWN = "unknown"
GROUPS = ("no functions", "with functions")


def predict_program(source: str) -> str:
    """Predicted class of a whole program: the class of its top-level code.

    How a call to one of the program's own functions is costed is up to
    estimate_complexity; until it handles calls, programs with functions
    will mostly be "unknown". Returns "unknown" if no graph can be built or
    the analysis is not implemented yet.
    """
    try:
        graph = build_graph(wrap_module(source))
    except GraphBuildError:
        return UNKNOWN
    try:
        predicted = estimate_complexity(graph)
    except NotImplementedError:
        return UNKNOWN
    if predicted not in COMPLEXITY_CLASSES:
        raise ValueError(f"estimate_complexity returned {predicted!r}, "
                         f"expected one of {COMPLEXITY_CLASSES}")
    return predicted


@dataclass(frozen=True)
class Prediction:
    program_id: int
    problem: str
    group: str  # one of GROUPS
    label: str
    predicted: str


def predict_all(programs: Iterable[Program]) -> list[Prediction]:
    return [
        Prediction(
            program_id=p.id,
            problem=p.problem,
            group=GROUPS[1] if p.has_functions else GROUPS[0],
            label=p.label,
            predicted=predict_program(p.src),
        )
        for p in programs
    ]


@dataclass
class Summary:
    programs: int = 0
    problems: int = 0
    correct: int = 0
    answered: int = 0  # predictions other than "unknown"
    problem_accuracy: float = 0.0  # mean over problems of each problem's accuracy
    confusion: Counter = field(default_factory=Counter)  # (label, predicted) -> count

    @property
    def accuracy(self) -> float:
        return self.correct / self.programs if self.programs else 0.0

    @property
    def coverage(self) -> float:
        return self.answered / self.programs if self.programs else 0.0

    @property
    def answered_accuracy(self) -> float:
        return self.correct / self.answered if self.answered else 0.0


def summarise(predictions: Iterable[Prediction]) -> Summary:
    s = Summary()
    per_problem: dict[str, list[bool]] = defaultdict(list)
    for p in predictions:
        hit = p.predicted == p.label
        s.programs += 1
        s.correct += hit
        s.answered += p.predicted != UNKNOWN
        s.confusion[(p.label, p.predicted)] += 1
        per_problem[p.problem].append(hit)
    s.problems = len(per_problem)
    if per_problem:
        s.problem_accuracy = sum(sum(h) / len(h) for h in per_problem.values()) / s.problems
    return s
