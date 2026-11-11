# pr-complexity

Static detection of complexity regressions in Python pull requests using
program graphs. University of Hertfordshire final year project (Daryl Ejoh,
supervisor Daniel Barry).

For each function a pull request changes, the tool will compare the new version
with the version after the previous merged pull request, estimate the
time-complexity class and the number of file, database and network calls of
both, and comment on the pull request only when the change makes things worse.
The code is never run.

## Status

| Part | Status |
|---|---|
| Program graphs (code_graph, pinned) behind our own interface | Done |
| Splitting files into functions and methods | Done |
| Command line: list functions, summarise and export graphs | Done |
| Top-level script code wrapped into a function for analysis | Done |
| CodeComplex dataset: download, loader, statistics | Done |
| Dev/test split and evaluation command | Done |
| Tests and CI (Linux, Windows, macOS) | Done |
| Loops, loop bounds, nesting | Weeks 4–6 |
| Recursion, built-in costs, external-call counting | Weeks 7–8 |
| Comparison with the previous version, pull request comment | Weeks 9–11 |

## Setup

Requires **Python 3.12** (3.10 and 3.11 also work). Python 3.13 is not supported
yet because the prebuilt grammar package has no 3.13 wheels.

```bash
python3.12 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.lock
pip install -e . --no-deps
pytest
```

With uv instead: `uv venv -p 3.12`, then `uv pip install` the same two lines.
Check `.venv/pyvenv.cfg` if imports fail: a venv made with macOS's built-in
Python 3.9 installs nothing useful.

No C compiler, git or network access is needed at run time.

## Evaluation data (CodeComplex)

4,900 Python solutions labelled with their time complexity, from
[sybaik1/CodeComplex-Data](https://github.com/sybaik1/CodeComplex-Data) at a
pinned commit. The repository states no licence, so the data is downloaded
into `data/` (git-ignored) rather than committed:

```bash
python scripts/fetch_codecomplex.py   # downloads and checks the SHA-256
pr-complexity codecomplex-stats       # programs per class, graph failures
pr-complexity codecomplex-eval        # accuracy on the dev split
pytest -m "not dataset"               # skip the ~30 s whole-dataset tests
```

The programs are split into **dev** (3,895 programs, 216 problems) for
developing and tuning the analysis and **test** (1,005 programs, 61
problems) for final results only (`codecomplex-eval --split test`). All
programs for one problem are on the same side, because most problems have a
single label. Each label's share is the same on both sides, overall and
within the "no functions" and "with functions" groups (see
`assign_splits`). `codecomplex-eval` reports coverage (answers other than
"unknown"), accuracy, accuracy averaged per problem (problems range from 1 to
138 programs) and confusion matrices; `--predictions out.csv` saves one row
per program.

Every program does its work at the top level, so it is analysed as
`wrap_module(src)` (top-level code as one function, line N → line N + 1)
plus each function from `split_functions(src)`.

## Usage

```bash
pr-complexity functions examples/single/merge_sort.py
pr-complexity graph examples/single/for_parameter.py --dot total.dot --no-syntax
dot -Tpng total.dot -o total.png     # needs Graphviz
```

In Python:

```python
from pr_complexity.graphs import build_graph, split_functions

graph = build_graph("def f(xs):\n    for x in xs:\n        print(x)\n")
graph.find("for_statement")          # loop nodes
graph.edge_counts()                  # Counter of edge kinds
```

## Layout

```
src/pr_complexity/   the tool
  graphs.py          the only module that talks to the graph library
  analysis.py        complexity analysis (not written yet)
  evaluation.py      scoring predictions: accuracy, coverage, confusion matrices
  cli.py             command line
  datasets/          evaluation datasets (CodeComplex loader and statistics)
scripts/             fetch_codecomplex.py
data/                downloaded datasets (git-ignored)
vendor/code_graph/   pinned copy of code_graph (see vendor/VENDORED.md)
examples/single/     labelled functions; first line is "# expected: <class>"
examples/pairs/      before/after pairs with expected.json
tests/               pytest suite; complexity tests are xfail until the analysis exists
```

## Pinned versions and why

| Package | Version | Reason |
|---|---|---|
| code_graph | commit `b03efd8` (Dec 2022), vendored | Not on PyPI; a pip install from GitHub misses its sub-packages |
| tree_sitter | 0.21.3 | code_graph's helpers use the API that was removed in 0.22 |
| tree_sitter_languages | 1.10.2 | Prebuilt grammars for 0.21; avoids cloning and compiling grammars |
| code_ast / code_tokenize | 0.1.2 / 0.2.1 | code_graph's helper packages |

The prebuilt Python grammar was checked against one compiled from
tree-sitter-python `v0.20.4`: the seven examples gave identical graphs.
Exact versions of everything are in `requirements.lock` and
`requirements-dev.lock`.

## Graph edges

| Kind | Meaning | Direction |
|---|---|---|
| `child`, `sibling`, `next_token` | Syntax tree and token order | parent → child |
| `controlflow`, `return_from` | What can run next | statement → next statement |
| `last_may_write`, `next_may_use`, `occurrence_of` | Data flow | write → read |

A loop shows up as a cycle of `controlflow` edges through its `for_statement`
or `while_statement` node.
