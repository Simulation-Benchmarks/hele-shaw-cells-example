"""Parse the heleShawFoam log file and the final-time alpha field.

Extracts the five metrics that go into solution_metrics.json:
  - phase1_volume_fraction       (cells with alpha > 0.5 / total cells)
  - cumulative_continuity_error  (last value of the cumulative entry)
  - interface_length_proxy       (cells with 0 < alpha < 1, proxy for perimeter)
  - wall_time_seconds            (ExecutionTime from the OF log)
  - time_step_count              (count of write-time dirs produced)

Pure stdlib (re + os) for portability.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any


def parse_log(log_path: Path) -> dict[str, Any]:
    """Extract ExecutionTime, cumulative continuity error, and phase-1
    volume fraction from the log.

    The OF solver prints `Phase-1 volume fraction = X` at every time
    step, where Phase-1 is the AIR phase (the discontinuous phase
    injected at the inlet). We use the LAST reported value (at endTime)
    for the metric.
    """
    log_path = Path(log_path)
    text = log_path.read_text(errors="replace") if log_path.exists() else ""

    # ExecutionTime / ClockTime lines look like:
    # "ExecutionTime = 1066.33 s  ClockTime = 1079 s"
    m = re.search(
        r"ExecutionTime\s*=\s*([\d.eE+-]+)\s*s\s*ClockTime\s*=\s*([\d.eE+-]+)\s*s",
        text,
    )
    execution_time = float(m.group(1)) if m else None
    clock_time = float(m.group(2)) if m else None

    # Final cumulative continuity error. Each time step prints
    # "time step continuity errors : sum local = ..., global = ..., cumulative = <val>"
    # We want the LAST cumulative value.
    cumulatives = re.findall(
        r"time step continuity errors\s*:\s*[^,]*,\s*[^,]*,\s*cumulative\s*=\s*([\d.eE+-]+)",
        text,
    )
    cumulative_continuity_error = float(cumulatives[-1]) if cumulatives else None

    # Phase-1 (air) volume fraction as printed by the solver.
    # Lines look like: "Phase-1 volume fraction = 0.211784  Min(alpha.air) = 0  Max(alpha.air) = 1"
    phase1_matches = re.findall(
        r"Phase-1 volume fraction\s*=\s*([\d.eE+-]+)",
        text,
    )
    phase1_volume_fraction = float(phase1_matches[-1]) if phase1_matches else None

    # Solver success signal
    end_ok = bool(re.search(r"^End\s*$", text, re.MULTILINE))

    return {
        "execution_time_seconds": execution_time,
        "clock_time_seconds": clock_time,
        "cumulative_continuity_error": cumulative_continuity_error,
        "phase1_volume_fraction_from_log": phase1_volume_fraction,
        "solver_completed": end_ok,
    }


def parse_alpha_field(path: Path) -> dict[str, int] | None:
    """Parse an OpenFOAM volScalarField and return phase statistics.

    Returns None if the file can't be parsed (e.g. uniform field with
    no cell list). For uniform fields, returns the per-cell-uniform
    classification based on the value.
    """
    path = Path(path)
    if not path.exists():
        return None
    text = path.read_text(errors="replace")

    # Uniform case
    m = re.search(
        r"internalField\s+uniform\s+(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*;",
        text,
    )
    if m:
        # Cannot compute per-cell statistics from a uniform field; the
        # caller is expected to read the post-setFields t=0 or a
        # post-run time dir. We just return None.
        return None

    # Non-uniform case
    m = re.search(
        r"internalField\s+nonuniform\s+List<scalar>\s+(\d+)\s*\(([^)]*)\)\s*;",
        text,
        re.DOTALL,
    )
    if not m:
        return None
    n = int(m.group(1))
    body = m.group(2)
    floats = [float(tok) for tok in body.split()]
    if len(floats) != n:
        return None

    n_air = sum(1 for v in floats if v > 0.5)
    n_interface = sum(1 for v in floats if 0.0 < v < 1.0)
    n_soap = sum(1 for v in floats if v < 0.5)  # includes 0
    return {
        "n_cells": n,
        "n_air_cells": n_air,
        "n_interface_cells": n_interface,
        "phase1_volume_fraction": n_air / n if n else 0.0,
        "interface_length_proxy": float(n_interface),
    }


def find_latest_time_dir(case_dir: Path) -> Path | None:
    """Return the directory under case_dir/Timesteps/ with the largest float name.

    The latest time directory is the one with the largest float-valued
    name (e.g. '15' > '0.05' > '0'). The OF case (and therefore all
    time-step dirs) lives under ``case_dir/Timesteps/``.
    """
    case_dir = Path(case_dir)
    timesteps_dir = case_dir / "Timesteps"
    if not timesteps_dir.is_dir():
        return None
    candidates: list[tuple[float, Path]] = []
    for entry in timesteps_dir.iterdir():
        if not entry.is_dir():
            continue
        try:
            t = float(entry.name)
        except ValueError:
            continue
        candidates.append((t, entry))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    return candidates[-1][1]


def count_time_step_dirs(case_dir: Path) -> int:
    """Count the time-step directories under case_dir/Timesteps/ (excludes 0 by default)."""
    case_dir = Path(case_dir)
    timesteps_dir = case_dir / "Timesteps"
    if not timesteps_dir.is_dir():
        return 0
    n = 0
    for entry in timesteps_dir.iterdir():
        if not entry.is_dir():
            continue
        try:
            float(entry.name)
        except ValueError:
            continue
        if entry.name == "0":
            continue
        n += 1
    return n


def extract_metrics(case_dir: Path) -> dict[str, Any]:
    """Compute the five metrics for solution_metrics.json from a finished run."""
    case_dir = Path(case_dir)
    log_info = parse_log(case_dir / "log.heleShawFoam")

    latest = find_latest_time_dir(case_dir)
    alpha_stats = None
    if latest is not None:
        alpha_stats = parse_alpha_field(latest / "alpha.air")

    metrics: dict[str, Any] = {
        # Phase-1 volume fraction as reported by the solver (integral of
        # alpha.air over the cell volumes, normalised). This is the
        # OF-reported ground truth, not the cell-fraction-with-alpha>0.5.
        "phase1_volume_fraction": log_info["phase1_volume_fraction_from_log"],
        "cumulative_continuity_error": log_info["cumulative_continuity_error"],
        "interface_length_proxy": (
            alpha_stats["interface_length_proxy"] if alpha_stats else None
        ),
        "wall_time_seconds": log_info["execution_time_seconds"],
        "time_step_count": count_time_step_dirs(case_dir),
    }
    return {
        "metrics": metrics,
        "log": {
            "solver_completed": log_info["solver_completed"],
            "execution_time_seconds": log_info["execution_time_seconds"],
            "clock_time_seconds": log_info["clock_time_seconds"],
        },
        "alpha_stats": alpha_stats,
        "latest_time": latest.name if latest else None,
    }
