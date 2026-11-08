"""Checks that the graph library is installed correctly and behaves as the
scope document describes (Figure 2): loops appear as control-flow cycles and
data flow links a loop's iterable back to the function's parameter."""

import pytest

from pr_complexity.graphs import (
    CONTROL_FLOW_EDGES,
    DATA_FLOW_EDGES,
    GraphBuildError,
    build_graph,
    has_syntax_error,
)

TOTAL = """
def total(orders):
    s = 0
    for o in orders:
        s += o.price
    return s
"""


def reaches(graph, start, goal, kinds):
    seen, stack = set(), [start]
    while stack:
        node = stack.pop()
        for nxt in graph.successors(node, kinds):
            if nxt.id == goal:
                return True
            if nxt.id not in seen:
                seen.add(nxt.id)
                stack.append(nxt.id)
    return False


def test_every_example_builds_a_graph(single_example):
    name, source, _ = single_example
    graph = build_graph(source)
    counts = graph.edge_counts()
    assert len(graph) > 0
    assert sum(counts[k] for k in CONTROL_FLOW_EDGES) > 0, name
    assert sum(counts[k] for k in DATA_FLOW_EDGES) > 0, name


def test_loop_is_a_control_flow_cycle():
    graph = build_graph(TOTAL)
    (loop,) = graph.find("for_statement", kind="syntax")
    assert reaches(graph, loop.id, loop.id, "controlflow")


def test_code_without_loops_has_no_cycle():
    graph = build_graph("def f(x):\n    y = x + 1\n    return y\n")
    statements = [n for n in graph if n.kind == "syntax" and n.label.endswith("statement")]
    assert statements
    assert not any(reaches(graph, n.id, n.id, "controlflow") for n in statements)


def test_loop_iterable_flows_from_parameter():
    graph = build_graph(TOTAL)
    uses = sorted((n for n in graph.find("orders", kind="token")), key=lambda n: n.line)
    parameter, in_loop_header = uses[0], uses[-1]
    assert parameter.line == 2 and in_loop_header.line == 4
    # Data-flow edges point from the write (the parameter) to the read.
    reads = graph.successors(parameter.id, "last_may_write")
    assert in_loop_header.id in {r.id for r in reads}


def test_nested_loops_are_both_found():
    graph = build_graph("def f(xs):\n    for a in xs:\n        for b in xs:\n            pass\n")
    assert len(graph.find("for_statement", kind="syntax")) == 2


def test_while_loop_is_found():
    graph = build_graph("def f(n):\n    while n > 1:\n        n = n // 2\n")
    (loop,) = graph.find("while_statement", kind="syntax")
    assert reaches(graph, loop.id, loop.id, "controlflow")


def test_syntax_error_is_rejected():
    assert has_syntax_error("def f(:\n    pass\n")
    with pytest.raises(GraphBuildError):
        build_graph("def f(:\n    pass\n")


def test_indented_method_source_is_accepted():
    graph = build_graph("    def m(self, xs):\n        for x in xs:\n            pass\n")
    assert graph.find("for_statement", kind="syntax")


def test_java_graph_builds():
    graph = build_graph("public int f(int[] a){ int s = 0; for (int x : a) { s += x; } return s; }",
                        lang="java")
    assert graph.edge_counts()["controlflow"] > 0


def test_dot_export():
    dot = build_graph(TOTAL).to_dot(include_syntax=False)
    assert dot.startswith("digraph") and "controlflow" in dot and "child" not in dot
