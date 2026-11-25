"""Recursion in CodeComplex: how much there is and what shape it takes (D2).

Usage: python experiments/recursion_survey/recursion_survey.py --examples 6 > results.json
Reads data/codecomplex/python_data.jsonl through the project's loader.
"""

import ast
import collections
import json
import sys
import warnings

from pr_complexity.datasets.codecomplex import load_codecomplex

SHAPES = [
    "memoised",
    "call inside a loop",
    "one call, argument shrinks by a constant",
    "one call, argument halves",
    "several calls, argument halves",
    "several calls, argument shrinks by a constant",
    "mutual recursion",
    "shrinkage not visible",
]


def called_name(call):
    """f(...) -> 'f'; self.f(...) -> 'f'; anything else -> None."""
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name):
        return call.func.attr if call.func.value.id in ("self", "cls") else None
    return None


def functions(tree):
    return [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def own_nodes(fn):
    """Nodes of fn's body, not descending into nested functions or lambdas."""
    stack = list(fn.body)
    while stack:
        node = stack.pop()
        yield node
        for child in ast.iter_child_nodes(node):
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                stack.append(child)


def parents_of(fn):
    parents = {}
    for node in [fn, *own_nodes(fn)]:
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def root_name(node):
    """dp[i][j][k] -> 'dp'; memo[x] -> 'memo'; anything else -> None."""
    while isinstance(node, ast.Subscript):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def is_memoised(fn):
    """lru_cache/cache decorator, or a table that is written by subscript and
    also tested (in an if, a comparison or an `in` check) before the work."""
    for d in fn.decorator_list:
        target = d.func if isinstance(d, ast.Call) else d
        name = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", "")
        if name in ("lru_cache", "cache"):
            return True
    written, tested = set(), set()
    for node in own_nodes(fn):
        if isinstance(node, (ast.Assign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Subscript):
                    written.add(root_name(t))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in ("get", "setdefault") and isinstance(node.func.value, ast.Name):
                tested.add(node.func.value.id)
        if isinstance(node, (ast.If, ast.IfExp)):
            for sub in ast.walk(node.test):
                if isinstance(sub, ast.Subscript):
                    tested.add(root_name(sub))
                if isinstance(sub, ast.Compare) and any(
                    isinstance(o, (ast.In, ast.NotIn)) for o in sub.ops
                ):
                    tested.update(c.id for c in sub.comparators if isinstance(c, ast.Name))
    return bool((written & tested) - {None})


def halving_names(fn):
    """Names assigned (a+b)//2, (a+b)>>1, n//2 or n>>1 inside fn."""
    names = set()
    for node in own_nodes(fn):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.BinOp):
            v = node.value
            if isinstance(v.op, (ast.FloorDiv, ast.RShift)) and isinstance(v.right, ast.Constant):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        names.add(t.id)
    return names


def argument_change(arg, params, halves):
    if isinstance(arg, ast.BinOp) and isinstance(arg.right, ast.Constant):
        left_is_var = isinstance(arg.left, ast.Name) and (
            arg.left.id in params or arg.left.id in halves
        )
        if left_is_var and isinstance(arg.op, (ast.FloorDiv, ast.RShift)):
            return "halves"
        if (
            isinstance(arg.left, ast.Name)
            and arg.left.id in halves
            and isinstance(arg.op, (ast.Add, ast.Sub))
        ):
            return "halves"  # mid - 1, mid + 1 in a binary search
        if isinstance(arg.left, ast.Name) and arg.left.id in params and isinstance(arg.op, ast.Sub):
            return "constant"
    if isinstance(arg, ast.Name) and arg.id in halves:
        return "halves"
    if isinstance(arg, ast.Subscript) and isinstance(arg.slice, ast.Slice):
        return (
            "halves"
            if any(isinstance(s, ast.Name) and s.id in halves for s in ast.walk(arg.slice))
            else "other"
        )
    return "other"


def classify(fn, self_calls, parents):
    if is_memoised(fn):
        return "memoised"
    for call in self_calls:
        p = parents.get(call)
        while p is not None and p is not fn:
            if isinstance(
                p,
                (
                    ast.For,
                    ast.While,
                    ast.comprehension,
                    ast.ListComp,
                    ast.SetComp,
                    ast.GeneratorExp,
                    ast.DictComp,
                ),
            ):
                return "call inside a loop"
            p = parents.get(p)
    params = {a.arg for a in fn.args.args}
    halves = halving_names(fn)
    changes = {argument_change(a, params, halves) for c in self_calls for a in c.args}
    several = len(self_calls) >= 2
    if "halves" in changes:
        return "several calls, argument halves" if several else "one call, argument halves"
    if "constant" in changes:
        return (
            "several calls, argument shrinks by a constant"
            if several
            else "one call, argument shrinks by a constant"
        )
    return "shrinkage not visible"


def survey_program(src):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree = ast.parse(src)
    except SyntaxError:
        return None
    fns = functions(tree)
    calls_by_fn = {fn: [n for n in own_nodes(fn) if isinstance(n, ast.Call)] for fn in fns}
    names = collections.Counter(fn.name for fn in fns)
    shapes = []
    for fn in fns:
        self_calls = [c for c in calls_by_fn[fn] if called_name(c) == fn.name]
        if self_calls:
            shapes.append((fn.name, fn.lineno, classify(fn, self_calls, parents_of(fn))))
    # mutual recursion: f -> g -> f with neither calling itself directly
    direct = {fn.name for fn in fns if any(called_name(c) == fn.name for c in calls_by_fn[fn])}
    graph = {fn.name: {called_name(c) for c in calls_by_fn[fn]} & set(names) for fn in fns}
    for f in graph:
        if f in direct:
            continue
        seen, stack = set(), list(graph[f] - {f})
        while stack:
            g = stack.pop()
            if g == f:
                line = next(fn.lineno for fn in fns if fn.name == f)
                shapes.append((f, line, "mutual recursion"))
                break
            if g in seen:
                continue
            seen.add(g)
            stack += graph.get(g, set())
    # keep only functions reachable from the program's top-level code
    reachable = reachable_functions(tree, fns, calls_by_fn)
    return [s for s in shapes if s[0] in reachable], shapes


def reachable_functions(tree, fns, calls_by_fn):
    """Names of functions called, directly or indirectly, from top-level code."""
    defined = {fn.name for fn in fns}
    top_calls = set()
    stack = list(tree.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        if isinstance(node, ast.Call):
            name = called_name(node)
            if name in defined:
                top_calls.add(name)
        # a name passed around (e.g. threading.Thread(target=main)) counts as a call
        if isinstance(node, ast.Name) and node.id in defined:
            top_calls.add(node.id)
        stack.extend(ast.iter_child_nodes(node))
    callees = collections.defaultdict(set)
    for fn in fns:
        for c in calls_by_fn[fn]:
            name = called_name(c)
            if name in defined:
                callees[fn.name].add(name)
        for node in own_nodes(fn):
            if isinstance(node, ast.Name) and node.id in defined:
                callees[fn.name].add(node.id)
    # class methods are reachable if their class is used; keep it simple and
    # treat every method of a class named in top-level code as reachable
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name in top_calls:
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    top_calls.add(item.name)
    seen, stack = set(), list(top_calls)
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        stack += callees.get(name, ())
    return seen


def main(argv):
    n_examples = int(argv[argv.index("--examples") + 1]) if "--examples" in argv else 0
    programs = load_codecomplex()
    labels = collections.Counter(p.label for p in programs)
    recursive = collections.Counter()
    defined_only = collections.Counter()
    shape_programs = collections.defaultdict(list)
    for p in programs:
        used, all_shapes = survey_program(p.src) or ([], [])
        if all_shapes and not used:
            defined_only[p.label] += 1
        if used:
            recursive[p.label] += 1
            for shape in {s for _, _, s in used}:
                shape_programs[shape].append(p)
    result = {
        "programs": len(programs),
        "recursive_programs": sum(recursive.values()),
        "recursion_defined_but_never_called": sum(defined_only.values()),
        "by_label": {
            lab: {"recursive": recursive[lab], "total": labels[lab]} for lab in sorted(labels)
        },
        "by_shape": {
            s: {
                "programs": len(shape_programs[s]),
                "labels": dict(
                    collections.Counter(p.label for p in shape_programs[s]).most_common()
                ),
            }
            for s in SHAPES
        },
    }
    if n_examples:
        result["examples"] = {s: [p.id for p in shape_programs[s][:n_examples]] for s in SHAPES}
    json.dump(result, sys.stdout, indent=1)


if __name__ == "__main__":
    main(sys.argv[1:])
