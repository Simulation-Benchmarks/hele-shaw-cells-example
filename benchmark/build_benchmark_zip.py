#!/usr/bin/env python3
"""benchmark/build_benchmark_zip.py — reproducibly package the benchmark bundle.

Renders openfoam/case_template/ with parameters_1.json (the reference
configuration) and packages the result with Allrun, Allclean, the mesh
generator, and the Results/ AVI into benchmark/hele-shaw-cells-example.zip.

The zip is what the runnable-repo's flow expects: a self-contained
OpenFOAM case directory. Anyone can unzip it and run `Allrun` directly
(or run `openfoam/run_simulation.py` against it).

This script is the source of truth for the zip. To re-build it after
changing the templates:

  python benchmark/build_benchmark_zip.py [--output benchmark/hele-shaw-cells-example.zip]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
CASE_TEMPLATE = REPO_ROOT / "openfoam" / "case_template"
PARAMS_FILE = REPO_ROOT / "parameters_1.json"
DEFAULT_OUTPUT = HERE / "hele-shaw-cells-example.zip"

sys.path.insert(0, str(REPO_ROOT / "openfoam"))
from _render_templates import render_case_template  # noqa: E402


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    ap.add_argument("--parameters-file", type=Path, default=PARAMS_FILE)
    ap.add_argument("--case-template-dir", type=Path, default=CASE_TEMPLATE)
    ap.add_argument("--include-results-avi", action="store_true",
                    help="Include the openfoam/case_template/Results/ AVI (~1.4 MB)")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    if not args.parameters_file.exists():
        print(f"ERROR: parameters file not found: {args.parameters_file}", file=sys.stderr)
        return 2
    if not args.case_template_dir.exists():
        print(f"ERROR: case_template dir not found: {args.case_template_dir}",
              file=sys.stderr)
        return 2

    parameters = json.loads(args.parameters_file.read_text())

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp) / "case"
        # Render the case template
        render_case_template(args.case_template_dir, parameters, tmpdir)

        # Replace the rendered system/blockMeshDict (it was rendered
        # with NPA=NPZ=80 from circulardomain.py, but the zip should
        # contain a blockMeshDict that matches parameters_1.json's mesh
        # settings). Re-run circulardomain.py to get the correct dict.
        from meshgen import circulardomain as cd  # type: ignore
        from math import sqrt
        cd.Rin = float(parameters["domain"]["R_in"])
        cd.Rout = float(parameters["domain"]["R_out"])
        cd.b = float(parameters["domain"]["b"])
        cd.NPA = int(parameters["mesh"]["NPA"])
        cd.NPZ = int(parameters["mesh"]["NPZ"])
        cd.NPB = int(parameters["mesh"]["NPB"])
        cd.b2 = cd.b / 2
        cd.r2i = cd.Rin / sqrt(2)
        cd.r2o = cd.Rout / sqrt(2)
        d = cd.create_dict("Rin", "Rout", "b", "b2", "NPA", "NPZ", "NPB", "r2i", "r2o")
        (tmpdir / "system" / "blockMeshDict").write_text(cd.t.substitute(d))

        # Drop the Results/ AVI unless asked
        results_avi = tmpdir / "Results"
        if not args.include_results_avi and results_avi.exists():
            shutil.rmtree(results_avi)

        # Write the zip. We DON'T include the parent "case/" prefix;
        # the zip root should look like an OF case directory.
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for f in sorted(tmpdir.rglob("*")):
                if f.is_file():
                    arcname = str(f.relative_to(tmpdir))
                    zf.write(f, arcname=arcname)

        size = args.output.stat().st_size
        print(f"build_benchmark_zip: wrote {args.output}  ({size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
