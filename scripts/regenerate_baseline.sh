#!/bin/sh
# scripts/regenerate_baseline.sh — re-run the benchmark and refresh the baselines.
#
# WARNING: this overwrites tests/baseline/metrics_baseline.json and the
# alpha field baselines. Only run this when the simulation has
# legitimately changed and the new outputs are correct.
#
# Usage:  scripts/regenerate_baseline.sh

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "regenerate_baseline.sh: running benchmark for configuration 1..."
python3 openfoam/run_benchmark.py --no-snakemake --configurations 1

echo "regenerate_baseline.sh: copying fresh metrics into baseline..."
cp results/1/solution_metrics.json tests/baseline/metrics_baseline.json

echo "regenerate_baseline.sh: extracting alpha fields from solution_field_data.zip..."
mkdir -p /tmp/regen
cd /tmp/regen
tar -xzf "$REPO_ROOT/results/1/solution_field_data.zip"
cp 0.05/alpha.air "$REPO_ROOT/tests/baseline/alpha.air_t0.05"
cp 15/alpha.air    "$REPO_ROOT/tests/baseline/alpha.air_t15"
cp log.heleShawFoam "$REPO_ROOT/tests/baseline/log.heleShawFoam"
cd "$REPO_ROOT"
rm -rf /tmp/regen

echo "regenerate_baseline.sh: done."
echo "  updated: tests/baseline/metrics_baseline.json"
echo "  updated: tests/baseline/alpha.air_t0.05, alpha.air_t15, log.heleShawFoam"
