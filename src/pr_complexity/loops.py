"""Finding the loops in one function's program graph (T3.1).

Statement loops (``for`` and ``while``) are found from the control flow, not
from the syntax: a loop is a *natural loop* around a back edge, i.e. an edge
from a statement to one that dominates it (every path from the function's
entry to the statement passes through that one first). This is the standard
definition used in compilers, and it handles ``break``, ``continue``,
``while True`` and ``for ... else`` without special cases.

Comprehensions and generator expressions (``[x for x in xs]``) loop too, but
their iterations happen inside a single statement, so they are invisible in
the control flow. Each ``for`` clause of a comprehension is reported as a
loop of its own, found from the syntax tree and nested under the loop that
runs it.

Loops inside nested functions and lambdas are left out: nested functions are
analysed on their own (see :func:`pr_complexity.graphs.split_functions`) and
the cost of calling a lambda is not known here.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .graphs import ProgramGraph

STATEMENT_LOOPS = {"for_statement": "for", "while_statement": "while"}
COMPREHENSIONS = frozenset(
    {"list_comprehension", "set_comprehension", "dictionary_comprehension", "generator_expression"}
)
FUNCTION_SCOPES = frozenset({"function_definition", "lambda"})


@dataclass(frozen=True)
class Loop:
    """One loop of a function.

    ``header`` is the node id of the ``for``/``while`` statement, or of the
    ``for`` clause of a comprehension. ``parent`` is the header of the
    innermost loop that runs this one, or None for a top-level loop.
    """

    header: int
    kind: str  # "for", "while" or "comprehension"
    line: int
    column: int
    depth: int  # 1 for a loop not inside another loop
    parent: int | None
    body: frozenset[int]  # control-flow statements inside the loop (empty for comprehensions)


def find_loops(graph: ProgramGraph) -> list[Loop]:
    """Return every loop of the function in ``graph``, in source order."""
    parents = _syntax_parents(graph)
    root = _root_function(graph, parents)
    statement_loops = _statement_loops(graph, parents, root)
    comprehension_loops = _comprehension_loops(graph, parents, root, statement_loops)

    found = {**statement_loops, **comprehension_loops}  # header -> (kind, body, parent)
    loops = []
    for header, (kind, body, parent) in found.items():
        node = graph.nodes[header]
        depth, p = 1, parent
        while p is not None:
            depth, p = depth + 1, found[p][2]
        loops.append(Loop(header, kind, node.line, node.column or 0, depth, parent, body))
    return sorted(loops, key=lambda loop: (loop.line, loop.column))


# --------------------------------------------------------------------------
# Syntax helpers
# --------------------------------------------------------------------------


def _syntax_parents(graph: ProgramGraph) -> dict[int, int]:
    return {e.target: e.source for e in graph.edges_of("child")}


def _root_function(graph: ProgramGraph, parents: dict[int, int]) -> int | None:
    """The outermost function_definition (None for a snippet without one).

    The graph may have a ``module`` node above it, e.g. when a comment comes
    before the ``def``.
    """

    def outermost(node_id):
        p = parents.get(node_id)
        while p is not None:
            if graph.nodes[p].label in FUNCTION_SCOPES:
                return False
            p = parents.get(p)
        return True

    roots = [n for n in graph.find("function_definition", "syntax") if outermost(n.id)]
    return min(roots, key=lambda n: (n.line, n.column)).id if roots else None


def _in_nested_scope(node_id: int, parents: dict[int, int], root: int | None,
                     graph: ProgramGraph) -> bool:
    """True if the node sits inside a function or lambda other than the root."""
    p = parents.get(node_id)
    while p is not None and p != root:
        if graph.nodes[p].label in FUNCTION_SCOPES:
            return True
        p = parents.get(p)
    return False


# --------------------------------------------------------------------------
# for and while loops, from the control flow
# --------------------------------------------------------------------------


def _statement_loops(graph, parents, root) -> dict[int, tuple[str, frozenset[int], int | None]]:
    # return_from edges lead back to the function itself and are not loops.
    succ: dict[int, set[int]] = defaultdict(set)
    pred: dict[int, set[int]] = defaultdict(set)
    for e in graph.edges_of("controlflow"):
        succ[e.source].add(e.target)
        pred[e.target].add(e.source)
    if not succ:
        return {}

    entry = root if root is not None else _first_statement(graph, succ, pred)
    order = _reachable_in_order(entry, succ)
    dom = _dominators(entry, order, pred)

    bodies: dict[int, set[int]] = defaultdict(set)
    for node in order:
        for target in succ[node]:
            if target in dom.get(node, ()):  # node -> target is a back edge
                bodies[target] |= _natural_loop(target, node, pred)

    loops = {}
    for header, body in bodies.items():
        label = graph.nodes[header].label
        if _in_nested_scope(header, parents, root, graph):
            continue
        # Python only loops through for and while; anything else is reported as such.
        loops[header] = (STATEMENT_LOOPS.get(label, label), frozenset(body), None)

    # A loop's parent is the smallest other loop whose body holds its header.
    result = {}
    for header, (kind, body, _) in loops.items():
        enclosing = [h for h, (_, b, _) in loops.items() if h != header and header in b]
        parent = min(enclosing, key=lambda h: len(loops[h][1])) if enclosing else None
        result[header] = (kind, body, parent)
    return result


def _first_statement(graph, succ, pred) -> int:
    starts = [n for n in succ if not pred[n]] or list(succ)
    return min(starts, key=lambda n: (graph.nodes[n].line or 0, graph.nodes[n].column or 0))


def _reachable_in_order(entry: int, succ: dict[int, set[int]]) -> list[int]:
    """Nodes reachable from entry, in reverse post-order (good order for dominators)."""
    seen, post = {entry}, []
    stack = [(entry, iter(sorted(succ[entry])))]
    while stack:
        node, children = stack[-1]
        child = next(children, None)
        if child is None:
            post.append(node)
            stack.pop()
        elif child not in seen:
            seen.add(child)
            stack.append((child, iter(sorted(succ[child]))))
    return post[::-1]


def _dominators(entry: int, order: list[int], pred: dict[int, set[int]]) -> dict[int, set[int]]:
    reachable = set(order)
    dom = {n: set(reachable) for n in order}
    dom[entry] = {entry}
    changed = True
    while changed:
        changed = False
        for node in order[1:]:
            preds = [dom[p] for p in pred[node] if p in reachable]
            new = set.intersection(*preds) | {node} if preds else {node}
            if new != dom[node]:
                dom[node], changed = new, True
    return dom


def _natural_loop(header: int, tail: int, pred: dict[int, set[int]]) -> set[int]:
    """The header plus every node that reaches the tail without passing the header."""
    body, stack = {header, tail}, [tail]
    while stack:
        for p in pred[stack.pop()]:
            if p not in body:
                body.add(p)
                stack.append(p)
    return body


# --------------------------------------------------------------------------
# Comprehension loops, from the syntax tree
# --------------------------------------------------------------------------


def _comprehension_loops(graph, parents, root, statement_loops):
    children: dict[int, list[int]] = defaultdict(list)
    for child, parent in parents.items():
        children[parent].append(child)

    def position(node_id):
        n = graph.nodes[node_id]
        return (n.line or 0, n.column or 0)

    def clauses(comprehension):
        found = [c for c in children[comprehension] if graph.nodes[c].label == "for_in_clause"]
        return sorted(found, key=position)

    def innermost_statement_loop(statement):
        """Innermost for/while loop that runs this statement every iteration."""
        holders = [h for h, (_, body, _) in statement_loops.items() if statement in body]
        if not holders:
            return None
        inner = min(holders, key=lambda h: len(statement_loops[h][1]))
        if inner == statement and graph.nodes[statement].label == "for_statement":
            # A comprehension in a for loop's header is its iterable: evaluated once.
            return statement_loops[inner][2]
        return inner

    cfg_nodes = {e.source for e in graph.edges_of("controlflow")}
    cfg_nodes |= {e.target for e in graph.edges_of("controlflow")}

    def context(comprehension):
        """The loop that runs a comprehension, walking out through the syntax tree."""
        previous, node = comprehension, parents.get(comprehension)
        while node is not None:
            label = graph.nodes[node].label
            if label in COMPREHENSIONS:
                own = clauses(node)
                if previous in own:  # inside the iterable of one of node's clauses
                    i = own.index(previous)
                    if i > 0:
                        return own[i - 1]
                    # the first clause's iterable is evaluated outside the comprehension
                else:  # in the element or an if clause: runs on every iteration
                    return own[-1]
            elif node in cfg_nodes:
                return innermost_statement_loop(node)
            previous, node = node, parents.get(node)
        return None

    loops = {}
    for comp in (n.id for n in graph if n.label in COMPREHENSIONS and n.kind == "syntax"):
        if _in_nested_scope(comp, parents, root, graph):
            continue
        outer = context(comp)
        for clause in clauses(comp):
            loops[clause] = ("comprehension", frozenset(), outer)
            outer = clause
    return loops
