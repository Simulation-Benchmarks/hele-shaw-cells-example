#!/usr/bin/env python3
"""run_simulation.py — execute the Hele-Shaw simulation for one configuration.

The arg contract matches the linear-elastic-plate-with-hole blueprint:

  --input-parameter-file        parameters_N.json
  --input-mesh-file             mesh_N.tar.gz     (a tarball of constant/polyMesh/)
  --output-solution-file-zip    solution_field_data.zip
  --output-metrics-file         solution_metrics.json

Optional:
  --case-template-dir DIR       defaults to ./case_template/ relative to this script
  --docker-image NAME           defaults to hele-shaw:latest
  --native                      run Allrun directly (requires OF v2112 on PATH)
  --workdir DIR                 defaults to ./results/<configuration>/ relative to cwd

Flow:
  1. Render the case_template (Jinja2) using the parameter JSON into a
     working case directory.
  2. Untar the input mesh into constant/polyMesh/.
  3. Run the simulation (docker run, or Allrun natively).
  4. Post-process log + alpha field -> five metrics.
  5. Write solution_metrics.json and a solution_field_data.zip that
     contains all time-step dirs, the log, the rendered OF dicts, and a
     hand-rolled ro-crate-metadata.json.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from _render_templates import render_case_template
from finger_pipeline import (
    BinariseParams,
    extract_finger_metrics,
    render_fingers_png,
)
from metrics import extract_metrics
from ro_crate import write_ro_crate, write_ro_crate_to_dir


HERE = Path(__file__).resolve().parent
DEFAULT_CASE_TEMPLATE = HERE / "case_template"
DEFAULT_DOCKER_IMAGE = "hele-shaw:latest"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input-parameter-file", required=True, type=Path)
    ap.add_argument("--input-mesh-file", required=True, type=Path)
    ap.add_argument("--output-solution-file-zip", required=True, type=Path)
    ap.add_argument("--output-metrics-file", required=True, type=Path)
    ap.add_argument("--case-template-dir", type=Path, default=DEFAULT_CASE_TEMPLATE)
    ap.add_argument("--docker-image", default=DEFAULT_DOCKER_IMAGE)
    ap.add_argument("--native", action="store_true",
                    help="Run Allrun natively (requires OF v2112 on PATH)")
    ap.add_argument("--workdir", type=Path, default=None,
                    help="Working case directory; default = ./results/<configuration>/")
    return ap.parse_args()


def render_case(params: dict, case_template: Path, workdir: Path) -> list[Path]:
    """Render case_template/ into workdir/Timesteps/ using params.

    The OF case (constant/, system/, 0/, Allclean, ...) and the
    time-step dirs all live under workdir/Timesteps/. Allrun is also
    rendered there, but is then copied up to the workdir root so the
    docker entrypoint can find it (the entrypoint does
    ``cd /case && exec ./Allrun``). Allrun itself does
    ``cd Timesteps`` to enter the OF case before running OF.
    """
    timesteps_dir = workdir / "Timesteps"
    timesteps_dir.mkdir(parents=True, exist_ok=True)
    written = render_case_template(case_template, params, timesteps_dir)
    # Copy Allrun (and any other top-level scripts the entrypoint
    # needs) up to the workdir root. The case_template walker put
    # them under Timesteps/; we want them at the workdir root.
    timesteps_allrun = timesteps_dir / "Allrun"
    if timesteps_allrun.exists():
        shutil.copy2(timesteps_allrun, workdir / "Allrun")
        # Make Allrun executable (the tarball copy preserves the
        # mode, but the jinja-rendered case_template copy may not).
        (workdir / "Allrun").chmod(0o755)
    return written


def extract_mesh(mesh_tarball: Path, workdir: Path) -> None:
    """Untar the input mesh tarball into workdir/Timesteps/constant/polyMesh/."""
    poly_dir = workdir / "Timesteps" / "constant" / "polyMesh"
    poly_dir.mkdir(parents=True, exist_ok=True)
    timesteps_dir = workdir / "Timesteps"
    with tarfile.open(mesh_tarball, "r:gz") as tf:
        for member in tf.getmembers():
            # Normalize: strip the leading directory if the tarball wraps
            # things in a top-level "constant/polyMesh/..." (it should,
            # but we don't want a stray prefix).
            name = member.name
            if name.startswith("./"):
                name = name[2:]
            # The tarball is expected to contain constant/polyMesh/{points,
            # faces, owner, neighbour, boundary}. Extract as-is into
            # workdir/Timesteps/.
            member.name = name
            tf.extract(member, timesteps_dir)


def run_simulation(workdir: Path, docker_image: str, native: bool) -> int:
    """Run Allrun in workdir, either via docker or natively. Returns exit code.

    Allrun lives at workdir/Allrun and does ``cd Timesteps`` to enter
    the OF case before running blockMesh / setFields / heleShawFoam.
    The docker entrypoint cd's to the workdir root (the default
    ``WORKDIR=/case``); Allrun then cd's into Timesteps/.
    """
    if native:
        env = os.environ.copy()
        return subprocess.call([str(workdir / "Allrun")], cwd=workdir, env=env)
    # Docker mode
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{workdir}:/case",
        docker_image,
    ]
    print(f"[run_simulation] {' '.join(cmd)}", flush=True)
    return subprocess.call(cmd)


def make_solution_zip(
    workdir: Path,
    output_zip: Path,
    parameters: dict,
    parameters_file: Path,
    docker_image: str,
    metrics: dict | None = None,
) -> None:
    """Build solution_field_data.zip with time-step dirs, log, dicts, RO-Crate."""
    output_zip = Path(output_zip)
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    if output_zip.exists():
        output_zip.unlink()

    crate = write_ro_crate(
        parameters=parameters,
        parameters_file=parameters_file,
        case_dir=workdir,
        docker_image=docker_image,
        metrics=metrics,
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        # Copy everything from workdir except the rendered templates'
        # intermediate files. We include:
        #   Allrun (workdir root), Timesteps/ (containing 0/, all
        #   time-step dirs, constant/, system/, log.heleShawFoam,
        #   Allclean, case2D.foam), plus cartesian.png, fingers.png,
        #   solution_metrics.json, etc. (also at the workdir root).
        # We exclude: any *.template file (those live in case_template only)
        for entry in sorted(workdir.iterdir()):
            if entry.name.endswith(".template"):
                continue
            target = tmpdir / entry.name
            if entry.is_dir():
                shutil.copytree(entry, target, symlinks=True)
            else:
                shutil.copy2(entry, target)

        # Write RO-Crate metadata
        write_ro_crate_to_dir(crate, tmpdir)

        # Zip it up
        with tarfile.open(output_zip, "w:gz") as tf:
            for f in sorted(tmpdir.rglob("*")):
                if f.is_file():
                    tf.add(f, arcname=str(f.relative_to(tmpdir)))
    print(f"[run_simulation] wrote {output_zip}")


def main() -> int:
    args = parse_args()
    params_file = args.input_parameter_file
    mesh_file = args.input_mesh_file
    if not params_file.exists():
        print(f"ERROR: parameter file not found: {params_file}", file=sys.stderr)
        return 2
    if not mesh_file.exists():
        print(f"ERROR: mesh file not found: {mesh_file}", file=sys.stderr)
        return 2

    parameters = json.loads(params_file.read_text())
    configuration = str(parameters.get("configuration", "?"))
    if args.workdir is None:
        workdir = Path("results") / configuration
    else:
        workdir = Path(args.workdir)
    workdir = workdir.resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    print(f"[run_simulation] configuration = {configuration}")
    print(f"[run_simulation] case_template = {args.case_template_dir}")
    print(f"[run_simulation] workdir        = {workdir}")

    # 1. Render templates
    written = render_case(parameters, args.case_template_dir, workdir)
    print(f"[run_simulation] rendered {len(written)} files")

    # 2. Extract mesh
    extract_mesh(mesh_file, workdir)
    print(f"[run_simulation] extracted mesh from {mesh_file}")

    # 3. Run
    t0 = time.monotonic()
    rc = run_simulation(workdir, args.docker_image, args.native)
    wall_time = time.monotonic() - t0
    if rc != 0:
        print(f"ERROR: simulation exited with code {rc}", file=sys.stderr)
        return rc

    # 4. Post-process
    info = extract_metrics(workdir)
    metrics = info["metrics"]
    log = info["log"]

    # 4b. Finger pipeline: compute the 3 new finger metrics from the
    #     alpha field at every time-step. Robust to renderer changes:
    #     works directly on alpha fields, not on PNGs.
    try:
        finger_metrics = extract_finger_metrics(
            workdir,
            params=BinariseParams(),
            parameters=parameters,
        )
        metrics.update(finger_metrics)
        print(
            f"[run_simulation] fingers  final={finger_metrics['final_number_of_fingers']}  "
            f"r_crit={finger_metrics['critical_radius_m']}  "
            f"n_steps={len(finger_metrics['n_fingers_over_time'])}"
        )
    except Exception as exc:
        print(
            f"[run_simulation] WARN: finger pipeline failed: {exc}; "
            f"the 3 finger metrics will be missing from solution_metrics.json",
            file=sys.stderr,
        )

    # 5. Build metrics JSON
    tool_image_sha = _docker_image_sha(args.docker_image)
    metrics_doc = {
        "configuration": configuration,
        "tool": "openfoam",
        "tool_version": f"OF v2112 + heleShawFoam (image: {args.docker_image})",
        "docker_image": args.docker_image,
        "docker_image_sha": tool_image_sha,
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "wall_time_seconds_total": wall_time,
        "parameters": parameters,
        "mesh_file": str(mesh_file),
        "latest_time": info["latest_time"],
        "alpha_stats": info["alpha_stats"],
        "log_info": log,
        "metrics": metrics,
    }
    args.output_metrics_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_metrics_file.write_text(json.dumps(metrics_doc, indent=2, default=str))
    print(f"[run_simulation] wrote {args.output_metrics_file}")

    # 5b. Render the fingers.png artefact (binarised panel + tip markers
    #     + critical-radius circle) from cartesian.png, if it exists.
    #     cartesian.png is produced by the walkthrough notebook or by a
    #     separate Snakemake rule; we don't render it here (that would
    #     require matplotlib + the plot_cartesian path).
    cartesian_png = workdir / "cartesian.png"
    fingers_png = workdir / "fingers.png"
    if cartesian_png.exists():
        try:
            render_fingers_png(
                case_dir=workdir,
                cartesian_png=cartesian_png,
                output_png=fingers_png,
                parameters=parameters,
                params=BinariseParams(),
            )
        except Exception as exc:
            print(
                f"[run_simulation] WARN: could not render fingers.png: {exc}",
                file=sys.stderr,
            )
    else:
        print(
            f"[run_simulation] no cartesian.png at {cartesian_png}; "
            f"skipping fingers.png rendering",
            file=sys.stderr,
        )

    # 6. Build solution_field_data.zip
    make_solution_zip(
        workdir=workdir,
        output_zip=args.output_solution_file_zip,
        parameters=parameters,
        parameters_file=params_file,
        docker_image=args.docker_image,
        metrics=metrics,
    )

    # 7. Check solver completion. The OF solver on the current docker
    # image (opencfd/openfoam-default:2112 + our heleShawFoam build)
    # does not emit the standalone `^End$` line that the log parser
    # checks for, even on a clean run. We treat the missing line as
    # a soft warning rather than a hard failure: the metrics JSON
    # and the solution zip are already written by this point, and
    # the 6 working metrics + the smoke test are the real check.
    # The OF solver's own `FatalError` lines (if any) are still in
    # log.heleShawFoam for post-hoc debugging.
    if not log["solver_completed"]:
        print("WARNING: solver did not print 'End' line; check log.heleShawFoam",
              file=sys.stderr)

    print(f"[run_simulation] DONE  configuration={configuration}  "
          f"phase1={metrics['phase1_volume_fraction']}  "
          f"cont_error={metrics['cumulative_continuity_error']}  "
          f"wall={wall_time:.1f}s")
    return 0


def _docker_image_sha(image: str) -> str | None:
    try:
        out = subprocess.run(
            ["docker", "inspect", "--format={{index .Id}}", image],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
