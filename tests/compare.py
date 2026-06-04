#!/usr/bin/env python3
"""
compare.py — regression check for the hele-shaw-cells runnable build.

Compares two OpenFOAM volScalarField files (typically alpha.air snapshots)
and reports the L-infinity (max absolute) difference, the mean absolute
difference, and the field total. Exits with status 0 if the L-inf
difference is within the configured tolerance, otherwise non-zero.

This is a *smoke test*, not bit-exact reproduction. OpenFOAM's isoAdvector
is not bit-reproducible across OF patch levels, gcc versions, or
non-default parallel runs, so we allow a generous tolerance.

Usage:
    python tests/compare.py BASELINE.case FRESH.case [--tol 0.05]

The script accepts either:
  * two OpenFOAM volScalarField files (e.g. testcase/0.05/alpha.air), or
  * two testcase root directories (in which case alpha.air from the latest
    time directory is used).

The script does not require numpy; it uses the standard library only.
"""

import argparse
import os
import re
import sys
from pathlib import Path


def parse_alpha_air(path):
    """Parse an OpenFOAM volScalarField ASCII file and return the field as
    a list of floats. Handles both 'uniform X' and 'nonuniform List<scalar>
    N ( v0 v1 ... )' internal fields."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()

    # Uniform case
    m = re.search(
        r"internalField\s+uniform\s+(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*;",
        text,
    )
    if m:
        value = float(m.group(1))
        # We don't know the cell count from a uniform file; return None
        # for the field and a flag so the caller can handle it.
        return {"uniform": True, "value": value, "length": None, "values": None}

    # Non-uniform case
    m = re.search(
        r"internalField\s+nonuniform\s+List<scalar>\s+(\d+)\s*\(([^)]*)\)\s*;",
        text,
        re.DOTALL,
    )
    if not m:
        raise ValueError(f"could not parse internalField in {path}")

    n = int(m.group(1))
    body = m.group(2)
    # Tolerate both "(" ")" with line breaks and inline.
    # Strip parens around vectors we may have mistakenly caught — alpha is
    # a scalar so no parens are valid; if we see '(' inside, fail loud.
    if "(" in body:
        raise ValueError(f"unexpected '(' in scalar list in {path}")
    floats = [float(tok) for tok in body.split()]
    if len(floats) != n:
        raise ValueError(
            f"header says {n} entries, parsed {len(floats)} in {path}"
        )
    return {"uniform": False, "value": None, "length": n, "values": floats}


def find_latest_alpha(case_dir):
    """Return the path to the most recent alpha.air in a testcase root.
    The latest time directory is the one with the largest float name."""
    case_dir = Path(case_dir)
    candidates = []
    for entry in case_dir.iterdir():
        if not entry.is_dir():
            continue
        try:
            t = float(entry.name)
        except ValueError:
            continue
        alpha = entry / "alpha.air"
        if alpha.exists():
            candidates.append((t, alpha))
    if not candidates:
        raise FileNotFoundError(f"no alpha.air under {case_dir}")
    candidates.sort(key=lambda x: x[0])
    return candidates[-1][1]


def diff_fields(a, b):
    """Return (linf, l1, length) for two parsed field dicts of equal length.
    If both are uniform, compare scalars; if lengths differ, raise."""
    if a["uniform"] and b["uniform"]:
        return abs(a["value"] - b["value"]), abs(a["value"] - b["value"]), 1
    if a["uniform"] != b["uniform"]:
        raise ValueError("one field is uniform, the other is non-uniform")
    if a["length"] != b["length"]:
        raise ValueError(
            f"length mismatch: {a['length']} vs {b['length']}"
        )
    av = a["values"]
    bv = b["values"]
    linf = 0.0
    l1 = 0.0
    for x, y in zip(av, bv):
        d = abs(x - y)
        if d > linf:
            linf = d
        l1 += d
    return linf, l1 / len(av), len(av)


def resolve_input(p):
    p = Path(p)
    if p.is_file():
        return p
    if p.is_dir():
        return find_latest_alpha(p)
    raise FileNotFoundError(p)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("baseline", help="baseline file or testcase root")
    ap.add_argument("fresh", help="fresh run file or testcase root")
    ap.add_argument(
        "--tol",
        type=float,
        default=0.05,
        help="L-infinity tolerance (default 0.05, alpha is in [0,1])",
    )
    args = ap.parse_args()

    base_path = resolve_input(args.baseline)
    fresh_path = resolve_input(args.fresh)

    print(f"compare.py: baseline = {base_path}")
    print(f"compare.py: fresh    = {fresh_path}")

    base = parse_alpha_air(base_path)
    fresh = parse_alpha_air(fresh_path)

    try:
        linf, l1, n = diff_fields(base, fresh)
    except ValueError as exc:
        print(f"compare.py: ERROR: {exc}")
        return 2

    print(
        f"compare.py: cells={n}  L_inf={linf:.6f}  L1_mean={l1:.6f}  "
        f"tol={args.tol}"
    )

    if linf <= args.tol:
        print("compare.py: PASS (within tolerance)")
        return 0
    print("compare.py: FAIL (above tolerance)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
