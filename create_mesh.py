#!/usr/bin/env python3
"""create_mesh.py — top-level mesh generation for the Hele-Shaw example.

Reads parameters_<config>.json, renders the mesh via the OF tool's
circulardomain.py + blockMesh, and packages the resulting
constant/polyMesh/ into mesh_<config>.tar.gz.

The blockMesh call is run inside the OF Docker image so we don't need
OF installed on the host. The host only needs Docker.

Usage:
    python create_mesh.py <configuration>
    python create_mesh.py 1
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
from pathlib import Path


HERE = Path(__file__).resolve().parent
DEFAULT_DOCKER_IMAGE = "hele-shaw:latest"
OF_TOOL_DIR = HERE / "openfoam"
CIRCULARDOMAIN = OF_TOOL_DIR / "meshgen" / "circulardomain.py"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("configuration", help="Configuration id (matches parameters_<id>.json)")
    ap.add_argument("--parameters-file", type=Path, default=None,
                    help="Path to parameters JSON (default: parameters_<id>.json at repo root)")
    ap.add_argument("--output", type=Path, default=None,
                    help="Output tarball path (default: mesh_<id>.tar.gz at repo root)")
    ap.add_argument("--docker-image", default=DEFAULT_DOCKER_IMAGE)
    ap.add_argument("--native", action="store_true",
                    help="Use a host OF v2112 install instead of docker")
    ap.add_argument("--keep-tmp", action="store_true",
                    help="Don't delete the temporary case dir after the run")
    return ap.parse_args()


def render_blockmesh_dict(parameters: dict, workdir: Path) -> None:
    """Run circulardomain.py with the parameter values to produce blockMeshDict.

    circulardomain.py reads Rin/Rout/b/NPA/NPZ from its local scope and
    prints the OF blockMeshDict to stdout. We patch the local scope via
    Python's import-and-exec trick.

    blockMesh also requires a minimal system/controlDict; we write a stub.
    """
    domain = parameters.get("domain", {})
    mesh = parameters.get("mesh", {})

    # Load circulardomain.py as a module
    import importlib.util
    spec = importlib.util.spec_from_file_location("circulardomain", str(CIRCULARDOMAIN))
    cd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cd)

    # Patch the module's globals
    cd.Rin = float(domain.get("R_in", 0.0015))
    cd.Rout = float(domain.get("R_out", 0.095))
    cd.b = float(domain.get("b", 0.001))
    cd.NPA = int(mesh.get("NPA", 60))
    cd.NPZ = int(mesh.get("NPZ", 60))
    cd.NPB = int(mesh.get("NPB", 1))

    # Recompute derived values
    cd.b2 = cd.b / 2
    from math import sqrt
    cd.r2i = cd.Rin / sqrt(2)
    cd.r2o = cd.Rout / sqrt(2)

    # Call create_dict then template substitution
    d = cd.create_dict("Rin", "Rout", "b", "b2", "NPA", "NPZ", "NPB", "r2i", "r2o")
    blockmesh_dict_text = cd.t.substitute(d)

    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "system").mkdir(exist_ok=True)
    (workdir / "system" / "blockMeshDict").write_text(blockmesh_dict_text)

    # blockMesh requires a minimal controlDict to parse at all
    control_dict_stub = """FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      controlDict;
}
application     blockMesh;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         0;
deltaT          0;
writeControl    timeStep;
writeInterval   1;
"""
    (workdir / "system" / "controlDict").write_text(control_dict_stub)


def run_blockmesh(workdir: Path, docker_image: str, native: bool) -> int:
    if native:
        env = os.environ.copy()
        return subprocess.call(["blockMesh"], cwd=workdir, env=env)
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{workdir}:/case",
        "-w", "/case",
        docker_image,
        "blockMesh",
    ]
    print(f"[create_mesh] {' '.join(cmd)}", flush=True)
    return subprocess.call(cmd)


def tar_poly_mesh(workdir: Path, output_tar: Path) -> None:
    """Tar the constant/polyMesh/ directory into output_tar (gzipped)."""
    poly_dir = workdir / "constant" / "polyMesh"
    if not poly_dir.exists() or not any(poly_dir.iterdir()):
        raise FileNotFoundError(f"no polyMesh at {poly_dir} — blockMesh did not run?")
    output_tar = Path(output_tar)
    output_tar.parent.mkdir(parents=True, exist_ok=True)
    if output_tar.exists():
        output_tar.unlink()
    with tarfile.open(output_tar, "w:gz") as tf:
        # Add with the prefix "constant/polyMesh/" so it can be untarred
        # back into a working case directory.
        for f in sorted(poly_dir.rglob("*")):
            if f.is_file():
                arcname = "constant/polyMesh/" + str(f.relative_to(poly_dir))
                tf.add(f, arcname=arcname)


def main() -> int:
    args = parse_args()
    config = str(args.configuration)

    params_file = args.parameters_file or (HERE / f"parameters_{config}.json")
    if not params_file.exists():
        print(f"ERROR: parameter file not found: {params_file}", file=sys.stderr)
        return 2
    parameters = json.loads(params_file.read_text())

    out_tar = args.output or (HERE / f"mesh_{config}.tar.gz")

    if out_tar.exists():
        print(f"[create_mesh] reusing existing {out_tar}")
        return 0

    print(f"[create_mesh] configuration = {config}")
    print(f"[create_mesh] parameters    = {params_file}")
    print(f"[create_mesh] output        = {out_tar}")

    # Use a project-local temp dir rather than /tmp: on macOS+colima,
    # bind-mounts from /tmp (or /private/tmp) into the docker VM may
    # not expose the nested directory depending on colima's allowed
    # paths. A project-local dir under the repo root always works.
    project_tmp = HERE / "results" / ".tmp_mesh"
    project_tmp.mkdir(parents=True, exist_ok=True)
    workdir = project_tmp / f"mesh_case_{config}"
    workdir.mkdir(parents=True, exist_ok=True)

    render_blockmesh_dict(parameters, workdir)
    rc = run_blockmesh(workdir, args.docker_image, args.native)
    if rc != 0:
        print(f"ERROR: blockMesh exited with code {rc}", file=sys.stderr)
        return rc
    tar_poly_mesh(workdir, out_tar)
    if args.keep_tmp:
        print(f"[create_mesh] tmp kept at {workdir}")
    else:
        shutil.rmtree(workdir, ignore_errors=True)
    print(f"[create_mesh] wrote {out_tar}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
