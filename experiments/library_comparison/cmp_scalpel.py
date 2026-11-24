"""Run Scalpel 1.0b0 on the labelled examples (in its own environment).

Usage: python cmp_scalpel.py <examples dir> > results_scalpel.json
"""

import glob
import json
import os
import sys
import time

from scalpel.cfg import CFGBuilder
from scalpel.SSA.const import SSA


def back_edges(function_cfg):
    """Control-flow edges that jump back to an earlier block (one per loop path)."""
    edges = []
    for block in function_cfg:
        for exit_ in block.exits:
            if exit_.target.id <= exit_.source.id:
                header = exit_.target.get_source().strip().splitlines()[-1][:40]
                edges.append((exit_.source.id, exit_.target.id, header))
    return edges


def outside_names_in_headers(function_cfg, edges):
    """Names used in loop headers that have no definition inside the function."""
    ssa, _ = SSA().compute_SSA(function_cfg)
    headers = {target for _, target, _ in edges}
    return sorted(
        {
            name
            for block in headers
            for uses in ssa.get(block, [])
            for name, defs in uses.items()
            if not defs
        }
    )


def main(examples):
    paths = sorted(glob.glob(f"{examples}/single/*.py")) + sorted(
        glob.glob(f"{examples}/pairs/*/*.py")
    )
    rows = []
    for path in paths:
        name = os.path.relpath(path, examples)
        with open(path, encoding="utf-8") as f:
            source = f.read()
        start = time.perf_counter()
        try:
            cfg = CFGBuilder().build_from_src("m", source)
        except Exception as exc:  # record the failure and carry on
            rows.append({"file": name, "ok": False, "err": str(exc)[:80]})
            continue
        ms = round((time.perf_counter() - start) * 1000, 1)
        for (_, function), function_cfg in cfg.functioncfgs.items():
            row = {"file": name, "function": function, "ok": True, "ms_file": ms}
            row["loops"] = back_edges(function_cfg)
            try:
                row["outside_names_in_headers"] = outside_names_in_headers(
                    function_cfg, row["loops"]
                )
                row["ssa_ok"] = True
            except Exception as exc:  # SSA can fail on unusual code
                row.update(ssa_ok=False, ssa_err=str(exc)[:80])
            rows.append(row)
    json.dump(rows, sys.stdout, indent=1)


if __name__ == "__main__":
    main(sys.argv[1])
