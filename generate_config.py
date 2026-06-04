#!/usr/bin/env python3
"""generate_config.py — emit workflow_config.json from parameters_*.json.

Mirrors the plate benchmark's convention: scan the repo root for
parameters_<id>.json, write a JSON file listing configurations and the
simulation tool(s) that will run them.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parameters-glob", default="parameters_*.json",
                    help="Glob for parameter files (default: parameters_*.json at repo root)")
    ap.add_argument("--tools", nargs="+", default=["openfoam"],
                    help="List of simulation tools to run (default: openfoam)")
    ap.add_argument("--output", type=Path, default=Path("workflow_config.json"),
                    help="Output config path (default: workflow_config.json)")
    ap.add_argument("--repo-root", type=Path, default=Path("."),
                    help="Repo root for the parameter glob (default: cwd)")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    config_ids: list[str] = []
    for params_file in sorted(args.repo_root.glob(args.parameters_glob)):
        try:
            data = json.loads(params_file.read_text())
        except json.JSONDecodeError as exc:
            print(f"WARNING: {params_file} is not valid JSON: {exc}")
            continue
        cfg = data.get("configuration")
        if cfg is None:
            print(f"WARNING: {params_file} has no 'configuration' key; skipping")
            continue
        config_ids.append(str(cfg))
    if not config_ids:
        print(f"ERROR: no parameter files matching {args.parameters_glob} found")
        return 1
    out = {
        "configurations": config_ids,
        "tools": list(args.tools),
    }
    args.output.write_text(json.dumps(out, indent=2) + "\n")
    print(f"generate_config: {len(config_ids)} configurations, {len(args.tools)} tool(s)")
    for cfg in config_ids:
        print(f"  - configuration = {cfg}")
    print(f"  - tools         = {args.tools}")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
