"""Command-line entry point.

    pr-complexity functions FILE              list the functions in a file
    pr-complexity graph FILE [--function F]   summarise a function's program graph
                             [--dot OUT.dot]  and optionally export it
    pr-complexity codecomplex-stats [--data FILE]
                                              count programs and graph failures
                                              in the CodeComplex dataset
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .datasets.codecomplex import DEFAULT_PATH, dataset_stats, load_codecomplex
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


def _cmd_codecomplex_stats(args: argparse.Namespace) -> int:
    path = Path(args.data)
    if not path.exists():
        print(f"error: {path} not found; run: python scripts/fetch_codecomplex.py",
              file=sys.stderr)
        return 2
    programs = load_codecomplex(path)
    print(f"Building graphs for {len(programs)} programs...", file=sys.stderr)
    stats = dataset_stats(programs)

    row = "{:<12} {:>9} {:>13} {:>15} {:>15}"
    print(f"CodeComplex: {path} ({len(programs)} programs)\n")
    print(row.format("label", "programs", "no functions", "with functions", "graph failures"))
    for label, s in [*stats.by_label.items(), ("total", stats.total)]:
        print(row.format(label, s.programs, s.no_functions, s.with_functions, s.failed))
    print(f"\nCode outside functions (needs wrapping): {stats.module_code} of {len(programs)}")
    print(f"Module graphs failed: {len(stats.module_failures)} of {len(programs)}")
    print(f"Function graphs failed: {len(stats.function_failures)} of {stats.functions}")
    for pid, error in stats.module_failures:
        print(f"  program {pid}: {error}")
    for pid, name, error in stats.function_failures:
        print(f"  program {pid}, {name}: {error}")
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

    p = sub.add_parser("codecomplex-stats",
                       help="count programs and graph failures in the CodeComplex dataset")
    p.add_argument("--data", default=str(DEFAULT_PATH),
                   help="path to python_data.jsonl (default: %(default)s)")
    p.set_defaults(func=_cmd_codecomplex_stats)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
