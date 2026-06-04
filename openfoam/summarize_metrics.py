#!/usr/bin/env python3
"""openfoam/summarize_metrics.py — post-processing plots for the sweep.

Reads results/summary.csv (produced by summarize_results.py) and emits
two PDF plots:

  - phase1_volume_fraction_vs_NPA.pdf
        For the mesh-refinement sweep (configurations with the same
        flow rate and varying NPA), phase1_volume_fraction vs NPA.
  - phase1_volume_fraction_vs_flow_rate.pdf
        For the flow-rate sweep (configurations with the same NPA and
        varying flow rate), phase1_volume_fraction vs flow rate.

If only one configuration is in the CSV, the script just prints a note
and exits 0 (no plot to draw).

This is the Hele-Shaw equivalent of the plate benchmark's
plot_metrics.py.
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--summary-csv", type=Path, default=Path("results/summary.csv"))
    ap.add_argument("--output-dir", type=Path, default=Path("results"),
                    help="Where to write the PDFs (default: results/)")
    return ap.parse_args()


def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        print(f"ERROR: {path} not found; run summarize_results.py first", file=sys.stderr)
        sys.exit(1)
    with path.open() as fh:
        return list(csv.DictReader(fh))


def plot_phase1_vs_npa(rows: list[dict], output: Path) -> bool:
    """Group rows by flow rate, plot phase1 vs NPA for each group."""
    by_flow: dict[float, list[tuple[int, float]]] = defaultdict(list)
    for r in rows:
        try:
            npa = int(r["NPA"])
            phi = float(r["phase1_volume_fraction"])
            q = float(r["inlet_volumetric_flow_rate"])
        except (KeyError, ValueError, TypeError):
            continue
        by_flow[q].append((npa, phi))
    # Need at least 2 distinct NPA values to draw a line
    plottable = {q: pts for q, pts in by_flow.items() if len(pts) >= 2}
    if not plottable:
        return False
    fig, ax = plt.subplots(figsize=(6, 4))
    for q, pts in sorted(plottable.items()):
        pts.sort()
        x = [p[0] for p in pts]
        y = [p[1] for p in pts]
        ax.plot(x, y, marker="o", label=f"Q = {q:g} m³/s")
    ax.set_xlabel("NPA (= NPZ) — mesh resolution")
    ax.set_ylabel("Phase-1 (air) volume fraction at endTime")
    ax.set_title("Mesh refinement sweep")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)
    return True


def plot_phase1_vs_flow_rate(rows: list[dict], output: Path) -> bool:
    """Group rows by NPA, plot phase1 vs flow rate for each group."""
    by_npa: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for r in rows:
        try:
            npa = int(r["NPA"])
            phi = float(r["phase1_volume_fraction"])
            q = float(r["inlet_volumetric_flow_rate"])
        except (KeyError, ValueError, TypeError):
            continue
        by_npa[npa].append((q, phi))
    plottable = {n: pts for n, pts in by_npa.items() if len(pts) >= 2}
    if not plottable:
        return False
    fig, ax = plt.subplots(figsize=(6, 4))
    for n, pts in sorted(plottable.items()):
        pts.sort()
        x = [p[0] for p in pts]
        y = [p[1] for p in pts]
        ax.plot(x, y, marker="o", label=f"NPA = NPZ = {n}")
    ax.set_xlabel("Inlet volumetric flow rate (m³/s)")
    ax.set_ylabel("Phase-1 (air) volume fraction at endTime")
    ax.set_title("Flow-rate sweep")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)
    return True


def main() -> int:
    args = parse_args()
    rows = load_rows(args.summary_csv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if not rows:
        print("summarize_metrics: no rows in summary; nothing to plot")
        return 0

    npa_plot = args.output_dir / "phase1_volume_fraction_vs_NPA.pdf"
    if plot_phase1_vs_npa(rows, npa_plot):
        print(f"summarize_metrics: wrote {npa_plot}")
    else:
        print("summarize_metrics: skipped phase1_vs_NPA.pdf "
              "(need ≥2 distinct NPA values at the same flow rate)")

    q_plot = args.output_dir / "phase1_volume_fraction_vs_flow_rate.pdf"
    if plot_phase1_vs_flow_rate(rows, q_plot):
        print(f"summarize_metrics: wrote {q_plot}")
    else:
        print("summarize_metrics: skipped phase1_vs_flow_rate.pdf "
              "(need ≥2 distinct flow rates at the same NPA)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
