"""Command-line entry point.

    pr-complexity functions FILE              list the functions in a file
    pr-complexity graph FILE [--function F]   summarise a function's program graph
                             [--dot OUT.dot]  and optionally export it
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .graphs import (
    CONTROL_FLOW_EDGES,
    DATA_FLOW_EDGES,
    SYNTAX_EDGES,
    GraphBuildError,
    build_graph,
    split_functions,
)


def _cmd_functions(args: argparse.Namespace) -> int:
    for fn in split_functions(Path(args.file).read_text(encoding="utf-8")):
        print(f"{fn.name}\tlines {fn.start_line}-{fn.end_line}")
    return 0


def _cmd_graph(args: argparse.Namespace) -> int:
    source = Path(args.file).read_text(encoding="utf-8")
    functions = split_functions(source)
    if args.function:
        matches = [f for f in functions if f.name == args.function]
        if not matches:
            print(f"error: no function named {args.function!r}", file=sys.stderr)
            return 2
        targets = matches
    else:
        targets = functions

    for fn in targets:
        try:
            graph = build_graph(fn.source)
        except GraphBuildError as exc:
            print(f"{fn.name}: {exc}", file=sys.stderr)
            return 1
        counts = graph.edge_counts()
        syntax, control, data = (sum(counts[k] for k in kinds)
                                 for kinds in (SYNTAX_EDGES, CONTROL_FLOW_EDGES, DATA_FLOW_EDGES))
        print(f"{fn.name} (lines {fn.start_line}-{fn.end_line}): {len(graph)} nodes, "
              f"{syntax} syntax, {control} control-flow, {data} data-flow edges")
        if args.dot:
            out = Path(args.dot)
            if len(targets) > 1:
                out = out.with_name(f"{out.stem}.{fn.name}{out.suffix}")
            out.write_text(graph.to_dot(include_syntax=not args.no_syntax), encoding="utf-8")
            print(f"  wrote {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pr-complexity", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("functions", help="list the functions in a Python file")
    p.add_argument("file")
    p.set_defaults(func=_cmd_functions)

    p = sub.add_parser("graph", help="summarise or export program graphs")
    p.add_argument("file")
    p.add_argument("--function", help="only this function (e.g. 'total' or 'Cls.method')")
    p.add_argument("--dot", help="write Graphviz DOT to this path")
    p.add_argument("--no-syntax", action="store_true",
                   help="leave syntax edges out of the DOT file")
    p.set_defaults(func=_cmd_graph)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
