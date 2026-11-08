"""Complexity and external-call analysis (to be built in weeks 4-8).

Planned order, following the scope document:
  1. loops and their bounds (control flow + data flow)      weeks 4-6
  2. nesting and loops in sequence                           weeks 4-6
  3. recursion, built-in costs, external-call counting       weeks 7-8
"""

from __future__ import annotations

from .graphs import ProgramGraph

COMPLEXITY_CLASSES = (
    "O(1)", "O(log n)", "O(n)", "O(n log n)", "O(n^2)", "O(n^3)", "exponential", "unknown",
)


def estimate_complexity(graph: ProgramGraph) -> str:
    """Return the worst-case time-complexity class of one function."""
    raise NotImplementedError("Complexity analysis is not implemented yet")
