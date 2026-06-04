#!/usr/bin/env python3
"""openfoam/summarize_results.py — aggregate per-config metrics into one table.

Reads each results/<config>/solution_metrics.json and produces:
  - results/summary.json: the same data, plus a per-config table
  - results/summary.csv:   a flat CSV ready for plotting

This is the Hele-Shaw equivalent of the plate benchmark's
summarize_results.py.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
METRIC_KEYS = [
    "phase1_volume_fraction",
    "cumulative_continuity_error",
    "interface_length_proxy",
    "wall_time_seconds",
    "time_step_count",
]


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("metrics_files", nargs="+", type=Path,
                    help="results/<config>/solution_metrics.json paths")
    ap.add_argument("--output", type=Path, default=Path("results/summary.json"))
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    rows = []
    for f in args.metrics_files:
        if not f.exists():
            print(f"WARNING: {f} not found, skipping", file=sys.stderr)
            continue
        data = json.loads(f.read_text())
        config = data.get("configuration", f.parent.name)
        mesh = data.get("parameters", {}).get("mesh", {})
        flow_rate = (
            data.get("parameters", {})
            .get("boundary_conditions", {})
            .get("inlet_volumetric_flow_rate")
        )
        row = {
            "configuration": config,
            "NPA": mesh.get("NPA"),
            "NPZ": mesh.get("NPZ"),
            "inlet_volumetric_flow_rate": flow_rate,
        }
        for k in METRIC_KEYS:
            row[k] = data.get("metrics", {}).get(k)
        row["source_file"] = str(f)
        rows.append(row)

    rows.sort(key=lambda r: str(r["configuration"]))

    summary = {
        "configurations": [str(r["configuration"]) for r in rows],
        "rows": rows,
        "metric_keys": METRIC_KEYS,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, default=str))
    print(f"summarize_results: wrote {args.output}  ({len(rows)} configurations)")

    csv_path = args.output.with_suffix(".csv")
    with csv_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            writer.writeheader()
            for r in rows:
                writer.writerow(r)
    print(f"summarize_results: wrote {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
