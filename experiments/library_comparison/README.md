# Graph library comparison (D1, week 6)

Compares code_graph (through `pr_complexity.graphs`) with Scalpel 1.0b0.
The decision and results are in `docs/d1-graph-library-decision.md`.

Scalpel is installed in a separate environment so it cannot change the
project's pinned dependencies.

```bash
# code_graph: the project's own environment
python experiments/library_comparison/cmp_codegraph.py examples > results_code_graph.json

# Scalpel: a separate environment
python3.12 -m venv .venv-scalpel
.venv-scalpel/bin/pip install python-scalpel==1.0b0
.venv-scalpel/bin/python experiments/library_comparison/cmp_scalpel.py examples > results_scalpel.json
```

`types_case.py` is the small file used to test Scalpel's type inference.
