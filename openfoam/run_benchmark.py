#!/usr/bin/env python3
"""openfoam/run_benchmark.py — direct runner for the hele-shaw-cells-example.

Mirrors the plate benchmark's fenics/run_benchmark.py:

  1. Extract benchmark/hele-shaw-cells-example.zip into a per-run work
     area (or skip if --skip-extract).
  2. Iterate parameters_<id>.json at the repo root.
  3. For each, run Snakemake (or invoke run_simulation.py directly with
     --no-snakemake).

CLI:
  python openfoam/run_benchmark.py [--skip-extract] [--no-snakemake]
       [--snakemake-args "..."] [--docker-image hele-shaw:latest]
       [--configurations 1 2 3]
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
DEFAULT_BENCHMARK_ZIP = REPO_ROOT / "benchmark" / "hele-shaw-cells-example.zip"
DEFAULT_DOCKER_IMAGE = "hele-shaw:latest"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--benchmark-zip", type=Path, default=DEFAULT_BENCHMARK_ZIP,
                    help="Path to benchmark/<id>.zip")
    ap.add_argument("--skip-extract", action="store_true",
                    help="Don't extract the benchmark zip; assume files are already in place")
    ap.add_argument("--no-snakemake", action="store_true",
                    help="Invoke run_simulation.py directly (skip Snakemake)")
    ap.add_argument("--snakemake-args", default="--cores 1",
                    help="Extra args to pass to snakemake (default: --cores 1)")
    ap.add_argument("--docker-image", default=DEFAULT_DOCKER_IMAGE)
    ap.add_argument("--configurations", nargs="*", default=None,
                    help="Subset of configurations to run (default: all)")
    ap.add_argument("--workdir", type=Path, default=None,
                    help="Where to extract the benchmark zip (default: a temp dir)")
    return ap.parse_args()


def extract_zip(zip_path: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(target)
    print(f"[run_benchmark] extracted {zip_path} -> {target}")


def discover_configurations(filter_ids: list[str] | None) -> list[str]:
    ids: list[str] = []
    for f in sorted(REPO_ROOT.glob("parameters_*.json")):
        cfg = f.stem.split("_", 1)[1]
        if filter_ids is not None and cfg not in filter_ids:
            continue
        ids.append(cfg)
    return ids


def run_one(
    config: str,
    args: argparse.Namespace,
    extracted_dir: Path | None,
) -> int:
    params_file = REPO_ROOT / f"parameters_{config}.json"
    mesh_file = REPO_ROOT / f"mesh_{config}.tar.gz"
    metrics_file = REPO_ROOT / "results" / config / "solution_metrics.json"
    zip_file = REPO_ROOT / "results" / config / "solution_field_data.zip"

    if not params_file.exists():
        print(f"ERROR: {params_file} not found", file=sys.stderr)
        return 1
    if not mesh_file.exists():
        print(f"[run_benchmark] generating mesh for configuration {config}...")
        rc = subprocess.call(
            [sys.executable, str(REPO_ROOT / "create_mesh.py"), config,
             "--docker-image", args.docker_image],
            cwd=str(REPO_ROOT),
        )
        if rc != 0:
            return rc

    workdir = REPO_ROOT / "results" / config
    workdir.mkdir(parents=True, exist_ok=True)

    if args.no_snakemake:
        cmd = [
            sys.executable, str(HERE / "run_simulation.py"),
            "--input-parameter-file", str(params_file),
            "--input-mesh-file", str(mesh_file),
            "--output-solution-file-zip", str(zip_file),
            "--output-metrics-file", str(metrics_file),
            "--workdir", str(workdir),
            "--docker-image", args.docker_image,
        ]
    else:
        # Use the openfoam sub-Snakefile with --config configuration=<id>
        cmd = [
            "snakemake",
            "--snakefile", str(HERE / "Snakefile"),
            "--directory", str(HERE),
            "--config", f"configuration={config}",
        ] + args.snakemake_args.split()

    print(f"[run_benchmark] configuration {config}: {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=str(REPO_ROOT))


def main() -> int:
    args = parse_args()

    extracted_dir: Path | None = None
    if not args.skip_extract:
        if not args.benchmark_zip.exists():
            print(f"WARNING: benchmark zip not found at {args.benchmark_zip}; "
                  f"skipping extract (use --skip-extract to silence this)")
        else:
            extracted_dir = args.workdir or (REPO_ROOT / "results" / ".extracted")
            if extracted_dir.exists():
                shutil.rmtree(extracted_dir, ignore_errors=True)
            extract_zip(args.benchmark_zip, extracted_dir)

    configs = discover_configurations(args.configurations)
    if not configs:
        print("ERROR: no configurations found", file=sys.stderr)
        return 1
    print(f"[run_benchmark] running {len(configs)} configuration(s): {configs}")

    failed = []
    for cfg in configs:
        rc = run_one(cfg, args, extracted_dir)
        if rc != 0:
            print(f"[run_benchmark] configuration {cfg} FAILED (rc={rc})",
                  file=sys.stderr)
            failed.append((cfg, rc))

    if failed:
        print(f"[run_benchmark] {len(failed)} of {len(configs)} failed: {failed}",
              file=sys.stderr)
        return 1
    print(f"[run_benchmark] all {len(configs)} configurations OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
