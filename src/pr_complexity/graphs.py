"""Program graphs for Python functions.

Top-level script code is handled by wrapping it into a function first
(:func:`wrap_module`).

This module is the only place that talks to the graph library. The rest of
the tool works with the small, stable types defined here (ProgramGraph,
Node, Edge), so the library can be swapped later (python_graphs, Scalpel,
Joern or a hand-written builder) without touching the analysis code.

The library used today is code_graph (Richter, 2022), vendored under
``vendor/code_graph`` at a fixed commit. See ``vendor/VENDORED.md``.
"""

from __future__ import annotations

import textwrap
import warnings
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

import tree_sitter_languages

SUPPORTED_LANGUAGES = ("python", "java")

# Edge kinds produced by code_graph, grouped by what they mean.
# Direction: data-flow edges point from where a value is written to where it
# is read, e.g. the parameter `orders` -last_may_write-> `orders` in a loop
# header. Control-flow edges point from a statement to what can run next.
SYNTAX_EDGES = frozenset({"child", "sibling", "next_token"})
CONTROL_FLOW_EDGES = frozenset({"controlflow", "return_from"})
DATA_FLOW_EDGES = frozenset({"last_may_write", "next_may_use", "occurrence_of"})


class GraphBuildError(Exception):
    """Raised when the source cannot be turned into a program graph."""


def get_language(lang: str):
    """Prebuilt tree-sitter grammar (silences a deprecation warning in 0.21)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        return tree_sitter_languages.get_language(lang)


def get_parser(lang: str):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        return tree_sitter_languages.get_parser(lang)


# --------------------------------------------------------------------------
# Library setup
# --------------------------------------------------------------------------

_code_graph = None


def _load_code_graph():
    """Import code_graph with grammars taken from tree_sitter_languages.

    By default code_graph's helper packages (code_ast and code_tokenize)
    download the *latest* grammar from GitHub and compile it, which needs
    git, a C compiler and network access, and the latest grammars no longer
    work with tree_sitter 0.21. Pointing both helpers at the precompiled
    grammars in tree_sitter_languages avoids all three problems.
    """
    global _code_graph
    if _code_graph is not None:
        return _code_graph

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        import code_ast.parsers as code_ast_parsers
        import code_tokenize.parsers as code_tokenize_parsers

        code_tokenize_parsers.load_language = get_language
        code_ast_parsers.load_language = get_language

        import code_graph

    _code_graph = code_graph
    return code_graph


# --------------------------------------------------------------------------
# Graph types
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Node:
    id: int
    kind: str  # "syntax", "token" or "symbol"
    label: str  # syntax type (e.g. "for_statement") or token/symbol text
    line: int | None = None  # 1-based line in the analysed source


@dataclass(frozen=True)
class Edge:
    source: int
    target: int
    kind: str


@dataclass
class ProgramGraph:
    lang: str
    source: str
    nodes: dict[int, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)

    # -- queries ------------------------------------------------------------

    def edges_of(self, kinds: str | Iterable[str]) -> list[Edge]:
        kinds = {kinds} if isinstance(kinds, str) else set(kinds)
        return [e for e in self.edges if e.kind in kinds]

    def successors(self, node_id: int, kinds: str | Iterable[str] | None = None) -> list[Node]:
        if kinds is not None:
            kinds = {kinds} if isinstance(kinds, str) else set(kinds)
        return [
            self.nodes[e.target]
            for e in self.edges
            if e.source == node_id and (kinds is None or e.kind in kinds)
        ]

    def find(self, label: str, kind: str | None = None) -> list[Node]:
        return [
            n for n in self.nodes.values()
            if n.label == label and (kind is None or n.kind == kind)
        ]

    def edge_counts(self) -> Counter:
        return Counter(e.kind for e in self.edges)

    def __iter__(self) -> Iterator[Node]:
        return iter(self.nodes.values())

    def __len__(self) -> int:
        return len(self.nodes)

    def to_dot(self, include_syntax: bool = True) -> str:
        """Return the graph in Graphviz DOT format (for figures and debugging)."""
        colours = {"controlflow": "#2f5d8c", "return_from": "#2f5d8c",
                   "last_may_write": "#d9822b", "next_may_use": "#d9822b",
                   "occurrence_of": "#9aa6b2"}
        lines = ["digraph G {", '  node [shape=box, fontname="Helvetica", fontsize=10];']
        for n in self.nodes.values():
            shape = "ellipse" if n.kind != "syntax" else "box"
            label = n.label.replace('"', '\\"')
            lines.append(f'  n{n.id} [label="{label}", shape={shape}];')
        for e in self.edges:
            if not include_syntax and e.kind in SYNTAX_EDGES:
                continue
            colour = colours.get(e.kind, "#c0c6cc")
            lines.append(f'  n{e.source} -> n{e.target} '
                         f'[label="{e.kind}", color="{colour}", fontsize=8];')
        lines.append("}")
        return "\n".join(lines)


# --------------------------------------------------------------------------
# Building graphs
# --------------------------------------------------------------------------


def has_syntax_error(source: str, lang: str = "python") -> bool:
    tree = get_parser(lang).parse(source.encode("utf-8"))
    return tree.root_node.has_error


def build_graph(
    source: str, lang: str = "python", allow_syntax_errors: bool = False
) -> ProgramGraph:
    """Build the program graph of a single function (or a small snippet).

    code_graph is designed for one function at a time; use
    :func:`split_functions` first when the source holds several.
    """
    if lang not in SUPPORTED_LANGUAGES:
        raise GraphBuildError(f"Unsupported language: {lang!r}")
    source = textwrap.dedent(source)
    if not allow_syntax_errors and has_syntax_error(source, lang):
        raise GraphBuildError("Source contains a syntax error")

    cg = _load_code_graph()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            raw = cg.codegraph(source, lang=lang, syntax_error="ignore")
    except Exception as exc:  # the library raises many exception types
        raise GraphBuildError(f"code_graph failed: {exc}") from exc

    return _convert(raw, lang, source)


def _convert(raw, lang: str, source: str) -> ProgramGraph:
    from code_graph.graph import SymbolNode, TokenNode

    graph = ProgramGraph(lang=lang, source=source)
    ids: dict[int, int] = {}

    def node_id(raw_node) -> int:
        key = id(raw_node)
        if key not in ids:
            ids[key] = len(ids)
        return ids[key]

    raw_nodes = list(raw)
    for raw_node in raw_nodes:
        nid = node_id(raw_node)
        if isinstance(raw_node, SymbolNode):
            kind, label, line = "symbol", str(raw_node.node_name()), None
        elif isinstance(raw_node, TokenNode):
            ast = raw_node.token.ast_node
            kind, label, line = "token", raw_node.token.text, ast.start_point[0] + 1
        else:
            ast = raw_node.ast_node
            kind, label, line = "syntax", ast.type, ast.start_point[0] + 1
        graph.nodes[nid] = Node(id=nid, kind=kind, label=label, line=line)

    for raw_node in raw_nodes:
        for _, edge_kind, target in raw_node.successors():
            graph.edges.append(Edge(node_id(raw_node), node_id(target), edge_kind))
    return graph


# --------------------------------------------------------------------------
# Splitting a file into functions
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class FunctionSource:
    name: str  # e.g. "total" or "OrderService.total"
    start_line: int  # 1-based, inclusive
    end_line: int  # 1-based, inclusive
    source: str  # dedented source of the function


_DEFINITIONS = frozenset({"function_definition", "class_definition", "decorated_definition"})

# Statements and clauses whose blocks can hold a def, e.g. a fallback under
# `except ImportError:` or helpers under `if __name__ == "__main__":`.
_DEF_CONTAINERS = frozenset({
    "block",
    "if_statement", "elif_clause", "else_clause",
    "for_statement", "while_statement",
    "try_statement", "except_clause", "except_group_clause", "finally_clause",
    "with_statement",
    "match_statement", "case_clause",
})


def split_functions(source: str) -> list[FunctionSource]:
    """Return every function and method in a Python file, including nested ones."""
    data = source.encode("utf-8")
    tree = get_parser("python").parse(data)
    found: list[FunctionSource] = []

    def walk(node, prefix: str) -> None:
        for child in node.children:
            target = child
            if child.type == "decorated_definition":
                target = child.child_by_field_name("definition") or child
            if target.type == "function_definition":
                name = target.child_by_field_name("name").text.decode()
                qualname = f"{prefix}{name}"
                text = data[target.start_byte:target.end_byte].decode("utf-8")
                indent = " " * target.start_point[1]
                found.append(FunctionSource(
                    name=qualname,
                    start_line=target.start_point[0] + 1,
                    end_line=target.end_point[0] + 1,
                    source=textwrap.dedent(indent + text),
                ))
                walk(target.child_by_field_name("body"), f"{qualname}.")
            elif target.type == "class_definition":
                name = target.child_by_field_name("name").text.decode()
                walk(target.child_by_field_name("body"), f"{prefix}{name}.")
            elif child.type in _DEF_CONTAINERS:
                walk(child, prefix)

    walk(tree.root_node, "")
    return found


# --------------------------------------------------------------------------
# Wrapping top-level code into a function
# --------------------------------------------------------------------------

MODULE_FUNCTION = "__module__"

# Removed only at module level: `from __future__` and `import *` are not
# allowed inside a function, and imports cost nothing for this analysis.
_MODULE_IMPORTS = frozenset({
    "import_statement", "import_from_statement", "future_import_statement",
})


def _module_removals(node, top: bool = True):
    """Yield, in source order, the nodes wrap_module replaces with ``pass``:
    functions and classes not nested in another one, and top-level imports."""
    for child in node.children:
        if child.type in _DEFINITIONS or (top and child.type in _MODULE_IMPORTS):
            yield child
        elif child.type in _DEF_CONTAINERS:
            yield from _module_removals(child, top=False)


def has_module_code(source: str) -> bool:
    """True if the file does work outside its functions (not just defining
    functions and classes, importing, or a docstring)."""
    tree = get_parser("python").parse(source.encode("utf-8"))
    for child in tree.root_node.named_children:
        if child.type in _DEFINITIONS | _MODULE_IMPORTS | {"comment"}:
            continue
        inner = [c.type for c in child.named_children]
        if child.type == "expression_statement" and inner == ["string"]:
            continue  # docstring
        return True
    return False


def wrap_module(source: str) -> str:
    """Turn a file's top-level code into one function, ``__module__``.

    code_graph builds graphs of functions, but scripts (such as every
    CodeComplex program) do their work at the top level. Functions, classes
    and top-level imports are each replaced by ``pass``; analyse them
    separately with :func:`split_functions`.

    Line breaks inside a replaced node are kept as backslash continuations,
    so line N of ``source`` is line N + 1 of the result, and a statement after
    a semicolon (``import sys; n = 1``) stays where it was. Tabs are expanded
    to 8 columns, as Python does, and code is indented by 4 more columns.

    Raises GraphBuildError if valid source does not end up entirely inside
    ``__module__``.
    """
    data = source.expandtabs(8).encode("utf-8")
    tree = get_parser("python").parse(data)
    parts, pos = [], 0
    for node in _module_removals(tree.root_node):
        parts.append(data[pos:node.start_byte])
        parts.append(b"pass" + b"\\\n" * data.count(b"\n", node.start_byte, node.end_byte))
        pos = node.end_byte
    parts.append(data[pos:])
    body = textwrap.indent(b"".join(parts).decode("utf-8"), "    ")
    wrapped = f"def {MODULE_FUNCTION}():\n{body}\n    pass\n"

    root = get_parser("python").parse(wrapped.encode("utf-8")).root_node
    outside = [c for c in root.named_children if c.type not in ("comment", "line_continuation")]
    if not root.has_error and len(outside) != 1:
        raise GraphBuildError(f"top-level code did not stay inside {MODULE_FUNCTION}()")
    return wrapped
