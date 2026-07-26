#!/usr/bin/env python3
"""
compare.py — regression check for the hele-shaw-cells-example benchmark.

Two modes:

  (a) alpha-field mode (legacy, from hele-shaw-cells-runnable):
        compare.py BASELINE.case FRESH.case [--tol 0.05]
      Compares two alpha.air volScalarField files (or two case
      directories, in which case the latest-time alpha.air is used) and
      reports L-infinity, L1-mean, and per-cell statistics.

  (b) metrics mode (new for the blueprint-aligned example):
        compare.py --metrics FRESH_METRICS.json BASELINE_METRICS.json \
                   [--tol-json @path/to/tolerances.json]
        or
        compare.py FRESH_METRICS.json BASELINE_METRICS.json \
                   --tol phase1_volume_fraction=0.05 \
                   --tol cumulative_continuity_error=0.001 \
                   ...
      Compares the five-metric dict (phase1_volume_fraction, cumulative_
      continuity_error, interface_length_proxy, wall_time_seconds,
      time_step_count) against a baseline, with per-metric tolerances.

Exit codes:
  0  PASS (all checks within tolerance)
  1  FAIL (one or more checks out of tolerance)
  2  ERROR (file not found, parse failure, etc.)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tarfile
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# alpha-field mode
# ---------------------------------------------------------------------------

def parse_alpha_air(path):
    """Parse an OpenFOAM volScalarField ASCII file."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()

    m = re.search(
        r"internalField\s+uniform\s+(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*;",
        text,
    )
    if m:
        value = float(m.group(1))
        return {"uniform": True, "value": value, "length": None, "values": None}

    m = re.search(
        r"internalField\s+nonuniform\s+List<scalar>\s+(\d+)\s*\(([^)]*)\)\s*;",
        text,
        re.DOTALL,
    )
    if not m:
        raise ValueError(f"could not parse internalField in {path}")
    n = int(m.group(1))
    body = m.group(2)
    if "(" in body:
        raise ValueError(f"unexpected '(' in scalar list in {path}")
    floats = [float(tok) for tok in body.split()]
    if len(floats) != n:
        raise ValueError(
            f"header says {n} entries, parsed {len(floats)} in {path}"
        )
    return {"uniform": False, "value": None, "length": n, "values": floats}


def find_latest_alpha_in_zip(zip_path: Path) -> dict | None:
    """Find the latest-time alpha.air inside a solution_field_data.zip."""
    candidates: list[tuple[float, bytes]] = []
    with tarfile.open(zip_path, "r:gz") as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            parts = member.name.split("/")
            if len(parts) != 2:
                continue
            try:
                t = float(parts[0])
            except ValueError:
                continue
            if parts[1] == "alpha.air":
                fh = tf.extractfile(member)
                if fh is not None:
                    candidates.append((t, fh.read()))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    return parse_alpha_air_bytes(candidates[-1][1])


def find_latest_alpha_in_dir(case_dir: Path) -> dict | None:
    candidates: list[tuple[float, Path]] = []
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
        return None
    candidates.sort(key=lambda x: x[0])
    return parse_alpha_air(str(candidates[-1][1]))


def parse_alpha_air_bytes(data: bytes) -> dict:
    text = data.decode("utf-8", errors="replace")
    m = re.search(
        r"internalField\s+uniform\s+(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*;",
        text,
    )
    if m:
        return {"uniform": True, "value": float(m.group(1)),
                "length": None, "values": None}
    m = re.search(
        r"internalField\s+nonuniform\s+List<scalar>\s+(\d+)\s*\(([^)]*)\)\s*;",
        text,
        re.DOTALL,
    )
    if not m:
        raise ValueError("could not parse alpha.air bytes")
    n = int(m.group(1))
    floats = [float(tok) for tok in m.group(2).split()]
    return {"uniform": False, "value": None, "length": n, "values": floats}


def diff_fields(a, b):
    if a["uniform"] and b["uniform"]:
        return abs(a["value"] - b["value"]), abs(a["value"] - b["value"]), 1
    if a["uniform"] != b["uniform"]:
        raise ValueError("one field is uniform, the other is non-uniform")
    if a["length"] != b["length"]:
        raise ValueError(f"length mismatch: {a['length']} vs {b['length']}")
    av, bv = a["values"], b["values"]
    linf, l1 = 0.0, 0.0
    for x, y in zip(av, bv):
        d = abs(x - y)
        if d > linf:
            linf = d
        l1 += d
    return linf, l1 / len(av), len(av)


def resolve_alpha_input(p: Path) -> dict:
    p = Path(p)
    if p.is_file() and p.suffix == ".zip":
        return find_latest_alpha_in_zip(p)
    if p.is_file() and "alpha.air" in p.name:
        return parse_alpha_air(str(p))
    if p.is_dir():
        return find_latest_alpha_in_dir(p)
    raise FileNotFoundError(p)


def run_alpha_mode(baseline: Path, fresh: Path, tol: float) -> int:
    try:
        b = resolve_alpha_input(baseline)
        f = resolve_alpha_input(fresh)
    except (FileNotFoundError, ValueError) as exc:
        print(f"compare.py: ERROR: {exc}", file=sys.stderr)
        return 2
    try:
        linf, l1, n = diff_fields(b, f)
    except ValueError as exc:
        print(f"compare.py: ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"compare.py: alpha mode  cells={n}  L_inf={linf:.6f}  "
          f"L1_mean={l1:.6f}  tol={tol}")
    if linf <= tol:
        print("compare.py: PASS (within tolerance)")
        return 0
    print("compare.py: FAIL (above tolerance)")
    return 1


# ---------------------------------------------------------------------------
# metrics mode
# ---------------------------------------------------------------------------

DEFAULT_METRIC_TOLERANCES: dict[str, float] = {
    "phase1_volume_fraction":       0.05,   # ±5% absolute
    "cumulative_continuity_error":  0.001,  # ±1e-3 absolute
    "interface_length_proxy":       50.0,   # ±50 cells
    "wall_time_seconds":            0.30,   # ±30% relative
    "time_step_count":              0.0,    # exact
    "final_number_of_fingers":      5.0,    # ±5 fingers
    "critical_radius_m":            0.005,  # ±5 mm
}


def parse_metric_tol_args(items: list[str]) -> dict[str, float]:
    """Parse --tol key=value pairs."""
    out: dict[str, float] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"--tol expects key=value, got {item!r}")
        k, v = item.split("=", 1)
        out[k.strip()] = float(v)
    return out


def load_tolerances_from_file(path: Path) -> dict[str, float]:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return {
        k: float(v) for k, v in data.items()
        if not (isinstance(v, str) and k.startswith("_"))
    }


def run_metrics_mode(
    baseline_path: Path,
    fresh_path: Path,
    tolerances: dict[str, float],
) -> int:
    def load_metrics(p: Path) -> dict:
        data = json.loads(p.read_text())
        if "metrics" in data and isinstance(data["metrics"], dict):
            return data["metrics"]
        # Otherwise treat the file as a flat metrics dict
        return {k: v for k, v in data.items()
                if not (isinstance(v, str) and k.startswith("_"))}

    try:
        baseline = load_metrics(baseline_path)
        fresh = load_metrics(fresh_path)
    except (FileNotFoundError, KeyError, json.JSONDecodeError) as exc:
        print(f"compare.py: ERROR: {exc}", file=sys.stderr)
        return 2

    tol = {**DEFAULT_METRIC_TOLERANCES, **tolerances}
    n_pass = 0
    n_fail = 0
    failures: list[str] = []
    for key in DEFAULT_METRIC_TOLERANCES:
        b = baseline.get(key)
        f = fresh.get(key)
        t = tol[key]
        if b is None or f is None:
            print(f"compare.py: {key}: SKIP (missing value)")
            continue
        if key == "wall_time_seconds" and b != 0:
            delta = abs(f - b) / abs(b)
            within = delta <= t
            metric = f"rel delta = {delta:.3f}"
        elif key == "time_step_count":
            within = (f == b)
            metric = f"baseline={b}  fresh={f}"
        else:
            delta = abs(f - b)
            within = delta <= t
            metric = f"|delta| = {delta:.4g}  (tol {t})"
        status = "PASS" if within else "FAIL"
        print(f"compare.py: {key}: {status}  "
              f"baseline={b}  fresh={f}  {metric}")
        if within:
            n_pass += 1
        else:
            n_fail += 1
            failures.append(key)
    print(f"compare.py: metrics mode  {n_pass} pass, {n_fail} fail")
    if n_fail == 0:
        print("compare.py: PASS (all metrics within tolerance)")
        return 0
    print(f"compare.py: FAIL  ({', '.join(failures)} out of tolerance)")
    return 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("baseline")
    ap.add_argument("fresh")
    ap.add_argument("--tol", type=float, default=0.05,
                    help="L-infinity tolerance for alpha-field mode (default 0.05)")
    ap.add_argument("--tol-json", type=str, default=None,
                    help="Path to a JSON of per-metric tolerances for metrics mode. "
                         "Prefix with '@' is optional.")
    ap.add_argument("--tol-key", dest="tol_keys", action="append", default=[],
                    help="Per-metric override: key=value (repeatable)")
    ap.add_argument("--metrics", action="store_true",
                    help="Force metrics mode (otherwise auto-detect by file extension)")
    args = ap.parse_args()

    base = Path(args.baseline)
    fresh = Path(args.fresh)
    if not base.exists():
        print(f"compare.py: ERROR: baseline not found: {base}", file=sys.stderr)
        return 2
    if not fresh.exists():
        print(f"compare.py: ERROR: fresh not found: {fresh}", file=sys.stderr)
        return 2

    is_metrics = (
        args.metrics
        or (base.suffix == ".json" and fresh.suffix == ".json")
    )
    if is_metrics:
        tolerances: dict[str, float] = {}
        if args.tol_json:
            p = Path(args.tol_json.lstrip("@"))
            tolerances.update(load_tolerances_from_file(p))
        if args.tol_keys:
            tolerances.update(parse_metric_tol_args(args.tol_keys))
        return run_metrics_mode(base, fresh, tolerances)
    return run_alpha_mode(base, fresh, args.tol)


if __name__ == "__main__":
    raise SystemExit(main())
