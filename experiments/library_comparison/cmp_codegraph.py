"""Run code_graph (through pr_complexity.graphs) on the labelled examples.

Usage: python cmp_codegraph.py <examples dir> > results_code_graph.json
"""

import glob
import json
import os
import sys
import time

from pr_complexity.graphs import build_graph, split_functions

LOOP_KINDS = ("for_statement", "while_statement")


def on_cycle(graph, node_id):
    """True if node_id can reach itself through controlflow edges."""
    seen = set()
    stack = [s.id for s in graph.successors(node_id, "controlflow")]
    while stack:
        current = stack.pop()
        if current == node_id:
            return True
        if current in seen:
            continue
        seen.add(current)
        stack += [s.id for s in graph.successors(current, "controlflow")]
    return False


def loops(graph):
    return [
        {"kind": kind, "line": node.line, "cycle": on_cycle(graph, node.id)}
        for kind in LOOP_KINDS
        for node in graph.find(kind, "syntax")
    ]


def params_reaching_loop_headers(graph):
    """Names on the def line with a data-flow edge into a loop header line."""
    def_line = min(n.line for n in graph.nodes.values() if n.line)
    loop_lines = {n.line for kind in LOOP_KINDS for n in graph.find(kind, "syntax")}
    param_tokens = [n for n in graph.nodes.values() if n.kind == "token" and n.line == def_line]
    hits = set()
    for token in param_tokens:
        for edge in graph.edges:
            if edge.source == token.id and edge.kind in ("last_may_write", "next_may_use"):
                target = graph.nodes[edge.target]
                if target.line in loop_lines:
                    hits.add(target.label)
    return sorted(hits)


def main(examples):
    paths = sorted(glob.glob(f"{examples}/single/*.py")) + sorted(
        glob.glob(f"{examples}/pairs/*/*.py")
    )
    rows = []
    for path in paths:
        with open(path, encoding="utf-8") as f:
            source = f.read()
        for fn in split_functions(source):
            row = {"file": os.path.relpath(path, examples), "function": fn.name}
            start = time.perf_counter()
            try:
                graph = build_graph(fn.source)
            except Exception as exc:  # record the failure and carry on
                row.update(ok=False, err=str(exc)[:80])
                rows.append(row)
                continue
            row.update(
                ok=True,
                ms=round((time.perf_counter() - start) * 1000, 1),
                loops=loops(graph),
                param_to_loop=params_reaching_loop_headers(graph),
                nodes=len(graph),
                edges=len(graph.edges),
            )
            rows.append(row)
    json.dump(rows, sys.stdout, indent=1)


if __name__ == "__main__":
    main(sys.argv[1])
