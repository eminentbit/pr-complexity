"""Command-line entry point.

    pr-complexity functions FILE              list the functions in a file
    pr-complexity graph FILE [--function F]   summarise a function's program graph
                             [--dot OUT.dot]  and optionally export it
    pr-complexity codecomplex-stats [--data FILE] [--split S]
                                              count programs and graph failures
                                              in the CodeComplex dataset
    pr-complexity codecomplex-eval [--data FILE] [--split S] [--predictions OUT.csv]
                                              accuracy and confusion matrices
                                              (dev split unless told otherwise)
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from .analysis import COMPLEXITY_CLASSES
from .datasets.codecomplex import (
    DEFAULT_PATH,
    LABELS,
    Program,
    dataset_stats,
    load_codecomplex,
    select,
)
from .evaluation import GROUPS, Prediction, predict_all, summarise
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


def _load_split(args: argparse.Namespace) -> list[Program] | None:
    path = Path(args.data)
    if not path.exists():
        print(f"error: {path} not found; run: python scripts/fetch_codecomplex.py",
              file=sys.stderr)
        return None
    programs = select(load_codecomplex(path), args.split)
    problems = len({p.problem for p in programs})
    print(f"CodeComplex: {path}, {args.split} split "
          f"({len(programs)} programs, {problems} problems)\n")
    print(f"Building graphs for {len(programs)} programs...", file=sys.stderr)
    return programs


def _cmd_codecomplex_stats(args: argparse.Namespace) -> int:
    programs = _load_split(args)
    if programs is None:
        return 2
    stats = dataset_stats(programs)

    row = "{:<12} {:>9} {:>13} {:>15} {:>15}"
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


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def _cmd_codecomplex_eval(args: argparse.Namespace) -> int:
    if args.split == "test":
        print("note: test split; use it for final results only, not while tuning",
              file=sys.stderr)
    programs = _load_split(args)
    if programs is None:
        return 2
    predictions = predict_all(programs)
    groups = {g: [p for p in predictions if p.group == g] for g in GROUPS}

    row = "{:<15} {:>9} {:>9} {:>9} {:>9} {:>12} {:>16}"
    print(row.format("group", "programs", "problems", "coverage", "accuracy",
                     "per problem", "when answered"))
    for name, preds in [*groups.items(), ("all", predictions)]:
        s = summarise(preds)
        print(row.format(name, s.programs, s.problems, _pct(s.coverage), _pct(s.accuracy),
                         _pct(s.problem_accuracy), _pct(s.answered_accuracy)))

    print("\nBy class, all programs (few problems behind a class = noisy accuracy):")
    row = "{:<12} {:>9} {:>9} {:>9} {:>9} {:>12}"
    print(row.format("label", "programs", "problems", "coverage", "accuracy", "per problem"))
    for label in LABELS.values():
        s = summarise(p for p in predictions if p.label == label)
        print(row.format(label, s.programs, s.problems, _pct(s.coverage), _pct(s.accuracy),
                         _pct(s.problem_accuracy)))

    for name, preds in groups.items():
        _print_confusion(f"Confusion matrix, {name} (rows: label, columns: predicted)", preds)

    if args.predictions:
        _write_predictions(Path(args.predictions), programs, predictions)
        print(f"\nwrote {args.predictions}")
    return 0


def _print_confusion(title: str, predictions: list[Prediction]) -> None:
    confusion = summarise(predictions).confusion
    columns = COMPLEXITY_CLASSES
    print(f"\n{title}")
    print(f"{'':<12}" + "".join(f"{c:>12}" for c in columns))
    for label in LABELS.values():
        print(f"{label:<12}" + "".join(f"{confusion[(label, c)]:>12}" for c in columns))


def _write_predictions(path: Path, programs: list[Program], predictions: list[Prediction]):
    splits = {p.id: p.split for p in programs}
    with open(path, "w", newline="", encoding="utf-8") as f:
        out = csv.writer(f)
        out.writerow(["id", "problem", "split", "group", "label", "predicted"])
        for p in predictions:
            out.writerow([p.program_id, p.problem, splits[p.program_id], p.group, p.label,
                          p.predicted])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pr-complexity",
                                     description=next(iter((__doc__ or "").splitlines()), None))
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
    p.add_argument("--split", choices=["dev", "test", "all"], default="all",
                   help="which programs to count (default: %(default)s)")
    p.set_defaults(func=_cmd_codecomplex_stats)

    p = sub.add_parser("codecomplex-eval",
                       help="score the complexity analysis on the CodeComplex dataset")
    p.add_argument("--data", default=str(DEFAULT_PATH),
                   help="path to python_data.jsonl (default: %(default)s)")
    p.add_argument("--split", choices=["dev", "test", "all"], default="dev",
                   help="which programs to score (default: %(default)s; "
                        "keep test for final results)")
    p.add_argument("--predictions", help="also write one row per program to this CSV file")
    p.set_defaults(func=_cmd_codecomplex_eval)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
