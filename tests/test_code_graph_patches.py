"""Regression tests for the fixes made to the vendored code_graph.

Each was found by running loop detection on the CodeComplex programs and is
described in vendor/VENDORED.md. Before the fixes, the loops in these
examples had no control flow at all, so they could not be analysed.
"""

from pr_complexity.graphs import build_graph


def incoming_control_flow(graph, node):
    return [graph.nodes[e.source].label for e in graph.edges_of("controlflow")
            if e.target == node.id]


def writes_reaching(graph, name, line):
    """Lines of the writes of ``name`` that reach its uses on ``line``."""
    uses = {n.id for n in graph.nodes.values()
            if n.kind == "token" and n.label == name and n.line == line}
    return sorted({graph.nodes[e.source].line for e in graph.edges_of("last_may_write")
                   if e.target in uses})


def test_else_after_elif_is_in_the_control_flow():
    graph = build_graph(
        "def f(n):\n"
        "    if n < 2:\n"
        "        x = 1\n"
        "    elif n < 5:\n"
        "        x = 2\n"
        "    elif n < 9:\n"
        "        x = 3\n"
        "    else:\n"
        "        for i in range(n):\n"
        "            print(i)\n"
    )
    (loop,) = graph.find("for_statement", "syntax")
    assert "if_statement" in incoming_control_flow(graph, loop)


def test_if_elif_without_else_can_take_no_branch():
    # Both branches return, so the loop is reached only when neither is taken.
    graph = build_graph(
        "def f(n, xs):\n"
        "    if n < 2:\n"
        "        return 0\n"
        "    elif n < 5:\n"
        "        return 1\n"
        "    for x in xs:\n"
        "        print(x)\n"
    )
    (loop,) = graph.find("for_statement", "syntax")
    assert "if_statement" in incoming_control_flow(graph, loop)


def test_data_flow_reaches_else_after_elif():
    graph = build_graph(
        "def f(n):\n"
        "    if n < 0:\n"
        "        x = 1\n"
        "    elif n == 0:\n"
        "        x = 2\n"
        "    else:\n"
        "        while n > 1:\n"
        "            n //= 2\n"
        "    return n\n"
    )
    # the parameter (line 1) and the halving (line 8) both reach the condition
    assert writes_reaching(graph, "n", 7) == [1, 8]


def test_with_block_is_in_the_control_flow():
    graph = build_graph(
        "def f(path, xs):\n"
        "    with open(path) as fp:\n"
        "        for x in xs:\n"
        "            fp.write(x)\n"
        "    return 1\n"
    )
    (loop,) = graph.find("for_statement", "syntax")
    assert incoming_control_flow(graph, loop)


def test_continue_in_loop_else_belongs_to_outer_loop():
    graph = build_graph(
        "def f(bfs, path):\n"
        "    for node in bfs:\n"             # 2
        "        for nei in path[node]:\n"   # 3
        "            if nei < 0:\n"
        "                break\n"
        "        else:\n"
        "            continue\n"             # 7: goes back to line 2
        "        break\n"
        "    return 1\n"
    )
    outer = [n for n in graph.find("for_statement", "syntax") if n.line == 2][0]
    assert "continue_statement" in incoming_control_flow(graph, outer)
