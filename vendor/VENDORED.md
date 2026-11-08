# Vendored: code_graph

| | |
|---|---|
| Source | https://github.com/cedricrupb/code_graph |
| Commit | `b03efd896de44a188d2c8777350b3571e673bede` (15 December 2022, latest at time of copying) |
| Copied on | 8 November 2026 |
| Licence | MIT (see `code_graph/LICENSE`) |
| Changes | None. The files are byte-for-byte copies of that commit. |

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
