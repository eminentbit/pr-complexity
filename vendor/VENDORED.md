# Vendored: code_graph

| | |
|---|---|
| Source | https://github.com/cedricrupb/code_graph |
| Commit | `b03efd896de44a188d2c8777350b3571e673bede` (15 December 2022, latest at time of copying) |
| Copied on | 8 November 2026 |
| Licence | MIT (see `code_graph/LICENSE`) |
| Changes | Four control-flow and data-flow fixes in `pylang/cfg.py` and `pylang/dataflow.py` (24 November 2026, see below). Everything else is a byte-for-byte copy of that commit. |

## Why it is vendored instead of installed with pip

1. It is not on PyPI.
2. Installing it from GitHub with `pip install git+...` produces a broken package:
   its `setup.py` lists only the top-level `code_graph` package, so the
   `pylang` and `javalang` sub-packages are missing and `import code_graph`
   fails. The project's README only supports `pip install -e .` from a clone.
3. It imports `code_tokenize` without declaring it as a dependency.

Keeping a fixed copy here makes the build reproducible and protects the project
if the upstream repository changes or disappears (risk R1 in the scope document).

## Grammar loading

code_graph's helpers (`code_ast`, `code_tokenize`) normally clone the newest
tree-sitter grammar from GitHub and compile it. Newer grammars are incompatible
with tree_sitter 0.21.3, and compiling needs git and a C compiler.
`src/pr_complexity/graphs.py` instead points both helpers at the prebuilt
grammars in `tree_sitter_languages==1.10.2`.

On 8 November 2026 this was checked against a grammar compiled from
tree-sitter-python tag `v0.20.4`: all seven Table 1 examples produced identical
graphs (same node counts and edge counts of every kind).

## Fixes made to the copy

Running loop detection (T3.1) on all 4,900 CodeComplex programs showed 124 of
13,280 function graphs where a `for` or `while` loop had no control flow at
all. Four bugs in code_graph caused all but 8 of them; the remaining 8 are
loops whose body always ends in `break` or `return`, so they never repeat and
are correctly not reported as loops. Each changed method is marked
`PATCHED for pr-complexity`, and `tests/test_code_graph_patches.py` fails on
the original code and passes on the fixed copy.

| # | Bug | Effect | Fix |
|---|---|---|---|
| 1 | `visit_if_statement` read only the first `alternative` child, but tree-sitter puts every `elif` and the `else` under that field | In `if ... elif ... else`, the `else` branch had no control flow (`ControlFlowVisitor`, `SubControlFlowVisitor`) and no data flow (`DataFlowVisitor`) | Walk every alternative, each starting from the state after the condition |
| 2 | With `elif` but no `else`, the path that takes no branch was dropped | Code after `if ...: return` / `elif ...: return` looked unreachable | Keep that path when there is no `else` |
| 3 | The generic `visit()` treats every `*_statement` as a single step, including `with_statement` | The body of a `with` block had no control flow | Added `visit_with_statement` to `ControlFlowVisitor` |
| 4 | `break`/`continue` in a loop's `else` clause were recorded against that loop and then discarded | `for ... else: continue` lost the outer loop's back edge | Restore the enclosing loop's lists before walking the `else` clause (`ControlFlowVisitor`) |

Effect on CodeComplex: function graphs with a loop missing from the control
flow went from 124 to the 8 that never repeat.
