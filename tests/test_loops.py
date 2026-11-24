"""Loop detection (T3.1): for and while loops from the control flow, and
comprehension loops from the syntax tree."""

from pathlib import Path

import pytest

from pr_complexity.graphs import build_graph, wrap_module
from pr_complexity.loops import find_loops


def loops_of(source):
    """(line, kind, depth, parent line) for every loop, in source order."""
    graph = build_graph(source)
    result = []
    for loop in find_loops(graph):
        parent = graph.nodes[loop.parent].line if loop.parent is not None else None
        result.append((loop.line, loop.kind, loop.depth, parent))
    return result


def body_lines(source, line):
    graph = build_graph(source)
    (loop,) = [lp for lp in find_loops(graph) if lp.line == line and lp.kind != "comprehension"]
    return sorted({graph.nodes[n].line for n in loop.body})


# --- for and while ------------------------------------------------------------


def test_no_loops():
    assert loops_of("def f(xs):\n    return sorted(xs)\n") == []


def test_for_loop():
    source = "def f(xs):\n    s = 0\n    for x in xs:\n        s += x\n    return s\n"
    assert loops_of(source) == [(3, "for", 1, None)]
    assert body_lines(source, 3) == [3, 4]


def test_while_loop():
    source = "def f(n):\n    while n > 1:\n        n //= 2\n    return n\n"
    assert loops_of(source) == [(2, "while", 1, None)]


def test_nested_loops():
    source = (
        "def f(xs):\n"
        "    for a in xs:\n"
        "        for b in xs:\n"
        "            print(a, b)\n"
    )
    assert loops_of(source) == [(2, "for", 1, None), (3, "for", 2, 2)]
    assert body_lines(source, 3) == [3, 4]


def test_loops_in_sequence_are_not_nested():
    source = (
        "def f(xs):\n"
        "    for a in xs:\n"
        "        print(a)\n"
        "    for b in xs:\n"
        "        print(b)\n"
    )
    assert loops_of(source) == [(2, "for", 1, None), (4, "for", 1, None)]


def test_three_levels():
    source = (
        "def f(xs):\n"
        "    for a in xs:\n"
        "        for b in xs:\n"
        "            for c in xs:\n"
        "                print(a, b, c)\n"
    )
    assert [depth for _, _, depth, _ in loops_of(source)] == [1, 2, 3]


def test_break_and_continue_stay_in_the_right_loop():
    source = (
        "def f(xs):\n"
        "    for a in xs:\n"           # 2
        "        if a < 0:\n"          # 3
        "            continue\n"       # 4
        "        for b in xs:\n"       # 5
        "            if b == a:\n"     # 6
        "                break\n"      # 7
        "            print(b)\n"       # 8
    )
    assert loops_of(source) == [(2, "for", 1, None), (5, "for", 2, 2)]
    # break leaves the inner loop, so it belongs to the outer loop only
    assert body_lines(source, 5) == [5, 6, 8]
    assert body_lines(source, 2) == [2, 3, 4, 5, 6, 7, 8]


def test_while_true_with_break():
    source = (
        "def f(n):\n"
        "    while True:\n"
        "        n -= 1\n"
        "        if n < 0:\n"
        "            break\n"
        "    return n\n"
    )
    assert loops_of(source) == [(2, "while", 1, None)]
    assert body_lines(source, 2) == [2, 3, 4]


@pytest.mark.parametrize("header", ["for x in xs:", "while xs:"])
def test_else_block_is_outside_the_loop(header):
    source = (
        "def f(xs):\n"
        f"    {header}\n"
        "        xs = xs[1:]\n"
        "    else:\n"
        "        print('done')\n"
        "    return xs\n"
    )
    assert body_lines(source, 2) == [2, 3]


def test_loop_after_return_is_unreachable():
    source = "def f(xs):\n    return 0\n    for x in xs:\n        print(x)\n"
    assert loops_of(source) == []


@pytest.mark.parametrize("end", ["return x", "break"])
def test_loop_that_cannot_repeat_is_not_reported(end):
    # Every path through the body leaves the loop, so it runs at most once.
    source = (
        "def f(xs):\n"
        "    for x in xs:\n"
        "        if x:\n"
        "            print(x)\n"
        f"        {end}\n"
        "    return None\n"
    )
    assert loops_of(source) == []


def test_loops_in_nested_function_are_left_out():
    source = (
        "def f(xs):\n"
        "    def g(ys):\n"
        "        for y in ys:\n"
        "            print(y)\n"
        "    return g(xs)\n"
    )
    assert loops_of(source) == []


# --- comprehensions -------------------------------------------------------------


def test_list_comprehension():
    assert loops_of("def f(xs):\n    return [x * 2 for x in xs]\n") == [
        (2, "comprehension", 1, None)
    ]


@pytest.mark.parametrize("expr", ["{x for x in xs}", "{x: 1 for x in xs}", "sum(x for x in xs)"])
def test_other_comprehensions(expr):
    assert loops_of(f"def f(xs):\n    return {expr}\n") == [(2, "comprehension", 1, None)]


def test_comprehension_with_two_clauses_is_nested():
    loops = loops_of("def f(xs):\n    return [a * b for a in xs for b in xs if a]\n")
    assert [(kind, depth) for _, kind, depth, _ in loops] == [
        ("comprehension", 1), ("comprehension", 2)
    ]


def test_comprehension_in_loop_body_is_nested():
    source = "def f(m):\n    for row in m:\n        print(sum(v for v in row))\n"
    assert loops_of(source) == [(2, "for", 1, None), (3, "comprehension", 2, 2)]


def test_comprehension_in_for_iterable_runs_once():
    source = "def f(m):\n    for r in [r for r in m]:\n        print(r)\n"
    assert [(kind, depth) for _, kind, depth, _ in loops_of(source)] == [
        ("for", 1), ("comprehension", 1)
    ]


def test_comprehension_in_while_condition_runs_every_iteration():
    source = "def f(xs):\n    while any(x > 0 for x in xs):\n        xs = xs[1:]\n"
    assert loops_of(source) == [(2, "while", 1, None), (2, "comprehension", 2, 2)]


def test_comprehension_inside_comprehension_element():
    loops = loops_of("def f(m):\n    return [[c for c in r] for r in m]\n")
    outer, inner = sorted(loops, key=lambda lp: lp[2])
    assert outer[2] == 1 and inner[2] == 2


def test_comprehension_in_lambda_is_left_out():
    source = "def f(xs):\n    return sorted(xs, key=lambda t: len([u for u in t]))\n"
    assert loops_of(source) == []


# --- whole programs ---------------------------------------------------------------


def test_script_wrapped_as_module():
    source = "n = int(input())\nfor i in range(n):\n    for j in range(i):\n        print(j)\n"
    loops = loops_of(wrap_module(source))
    assert [(line - 1, kind, depth) for line, kind, depth, _ in loops] == [
        (2, "for", 1), (3, "for", 2)
    ]


EXPECTED_LOOPS = {
    # example: (number of loops, deepest nesting)
    "binary_search": (1, 1),
    "constant_range": (1, 1),
    "for_parameter": (1, 1),
    "halving_while": (1, 1),
    "input_bound": (1, 1),
    "loops_in_sequence": (3, 2),
    "merge_sort": (1, 1),
    "nested_loops": (2, 2),
    "sorted_call": (0, 0),
}


def test_labelled_examples(single_example):
    name, source, _ = single_example
    loops = find_loops(build_graph(source))
    assert (len(loops), max((lp.depth for lp in loops), default=0)) == EXPECTED_LOOPS[name]


# --- CodeComplex ------------------------------------------------------------------

DATA = Path(__file__).resolve().parent.parent / "data" / "codecomplex" / "python_data.jsonl"


def _can_repeat(graph, header):
    """True if some statement inside the loop jumps back to its header."""
    parents = {e.target: e.source for e in graph.edges_of("child")}

    def inside(node_id):
        p = parents.get(node_id)
        while p is not None:
            if p == header:
                return True
            p = parents.get(p)
        return False

    return any(e.target == header and inside(e.source) for e in graph.edges_of("controlflow"))


@pytest.mark.dataset
@pytest.mark.skipif(not DATA.exists(), reason="run scripts/fetch_codecomplex.py first")
def test_codecomplex_statement_loops():
    """On every CodeComplex graph, a for/while statement outside nested functions
    is reported exactly when a statement inside it can jump back to it."""
    from pr_complexity.datasets.codecomplex import load_codecomplex
    from pr_complexity.graphs import split_functions
    from pr_complexity.loops import FUNCTION_SCOPES

    wrong = []
    for program in load_codecomplex(DATA):
        units = [("__module__", wrap_module(program.src))]
        units += [(fn.name, fn.source) for fn in split_functions(program.src)]
        for name, source in units:
            graph = build_graph(source)
            parents = {e.target: e.source for e in graph.edges_of("child")}
            reported = {lp.header for lp in find_loops(graph)}
            for node in graph.nodes.values():
                if node.label not in ("for_statement", "while_statement"):
                    continue
                scopes, p = 0, parents.get(node.id)
                while p is not None:
                    scopes += graph.nodes[p].label in FUNCTION_SCOPES
                    p = parents.get(p)
                if scopes > 1:  # inside a nested function
                    continue
                if (node.id in reported) != _can_repeat(graph, node.id):
                    wrong.append((program.id, name, node.line))
    assert wrong == []
