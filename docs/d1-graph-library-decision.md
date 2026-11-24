# D1: graph library decision (week 6)

**Decision (24 November 2026):** keep code_graph, vendored at commit `b03efd8`.
Scalpel is not adopted, including for type inference (T8.1).

## Method

I ran code_graph (through `src/pr_complexity/graphs.py`) and Scalpel 1.0b0
on Python 3.12, on the 9 labelled examples in `examples/single/` and the 2
functions in `examples/pairs/attach_customers/` (11 functions, 13 loops).
For each function I checked:

1. whether a graph builds;
2. whether every loop is found;
3. whether the loop header can be traced back to a parameter, which is what
   the loop-bound rule in T3.2 needs;
4. for Scalpel only, whether its type inference can tell a set or a dict from
   a list, which is why it was considered for T8.1.

The scripts and raw results are in `experiments/library_comparison/`.

## Results

| Check | code_graph | Scalpel 1.0b0 |
|---|---|---|
| Graphs built | 11 of 11 | 11 of 11 |
| Loops found | 13 of 13, each as a cycle of `controlflow` edges through its `for`/`while` node | 13 of 13, but as 16 back edges: loops with branches (binary search, merge sort, nested loops) give more than one, so they must be grouped by loop header |
| Loop header traced to a parameter | 6 of 11 functions | 5 of 11: misses `n` in `while n > 1` (`halving_while`), because its SSA has no entry for the parameter |
| Noise in results | None | Built-ins (`range`, `len`, `input`, `int`) appear as names from outside the function and must be filtered |
| Type inference | None | `seen = set()` and a dict comprehension both come out as `any`; only lists are recognised |
| Graph detail | Token level, one function at a time | Basic blocks, whole module, plus a call graph (PyCG) |
| Last release | December 2022 (vendored copy) | v1.0b0, December 2022; repository last pushed March 2024 |

## Why code_graph

- It traces more loop bounds back to parameters, which is the core of the
  loop-bound rule.
- My interface, function splitting, tests and CI already work with it.
- Scalpel is no better maintained, so switching would not reduce risk R1.
- Scalpel's type inference fails on exactly the case T8.1 needs: telling a
  set lookup (O(1)) from a list scan (O(n)).

## Consequences for the plan

- **T3** builds on code_graph through `graphs.py`, as planned.
- **T8.1** will infer types from assignments in my own code (`set()`, `{}`,
  `[]`, `dict()`, `list()` and comprehensions) instead of using Scalpel.
- **Could feature (analysis across functions):** Scalpel's call graph is still
  an option if that feature is attempted.
- **T3.2:** neither library traces `binary_search`'s bound directly, because it
  comes through `lo, hi = 0, len(a)`. The loop-bound rule must follow
  assignments back to parameters, not only direct uses.
