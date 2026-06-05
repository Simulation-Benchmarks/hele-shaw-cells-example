"""Build notebooks/Simulation_Walkthrough.ipynb programmatically.

This script emits the 30-cell walkthrough notebook as a JSON file
matching the Jupyter v4.5 spec. We do not use the `nbformat` package
to avoid adding it as a runtime dep — the JSON is built directly.

Run from the repo root: `python scripts/build_walkthrough_notebook.py`
"""
from __future__ import annotations

import json
import secrets
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "notebooks" / "Simulation_Walkthrough.ipynb"


def _cell_id() -> str:
    """Random 8-hex-digit cell id (matches Jupyter's own id format)."""
    return secrets.token_hex(4)


def md(*lines: str) -> dict:
    """A markdown cell. Each line is suffixed with \\n per the Jupyter
    convention (see linear-elastic-plate-with-hole/notebooks/RoCrate.ipynb)."""
    return {
        "id": _cell_id(),
        "cell_type": "markdown",
        "metadata": {},
        "source": [line if line.endswith("\n") else line + "\n" for line in lines],
    }


def code(*lines: str) -> dict:
    """A code cell. Each line is suffixed with \\n per the Jupyter convention."""
    return {
        "id": _cell_id(),
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [line if line.endswith("\n") else line + "\n" for line in lines],
    }


def build_cells() -> list[dict]:
    cells: list[dict] = []

    # ============================================================
    # Section 1: Clone the repo (cells 1-2)
    # ============================================================
    cells.append(md(
        "# Hele-Shaw Cells — Simulation Walkthrough",
        "",
        "This notebook walks you through the **hele-shaw-cells-example**",
        "benchmark end-to-end: from cloning the repo, to building the",
        "OpenFOAM Docker image, to running the simulation, to inspecting",
        "the fingers and the metrics.",
        "",
        "**Prerequisites**",
        "",
        "- Docker (≥ 20.10). Get it from <https://docs.docker.com/get-docker/>.",
        "- On macOS with Colima: run `colima start` before launching Jupyter.",
        "  The notebook shells out to `docker`; if the daemon is down you'll",
        "  get a `FileNotFoundError` (we deliberately do not guard the call).",
        "- Python 3.10 or newer.",
        "- About 2 GB of free disk space (the Docker image is 1.83 GB).",
        "- About 1 GB more for the simulation output (~720 MB for the full run).",
        "",
        "**Expected runtime on a native amd64 host**: 10-15 minutes (dominated",
        "by the simulation itself; each configuration takes 3-5 minutes).",
        "",
        "**On an arm64 host (e.g. Apple Silicon)**: ~30-60 minutes. The",
        "`opencfd/openfoam-default:2112` base image is amd64-only; Docker uses",
        "QEMU emulation, which adds roughly 4× overhead but produces identical",
        "results.",
        "",
        "**Where to get help**",
        "",
        "- Mathematical model: see `docs/hele-shaw-cells.md` in this repo.",
        "- Troubleshooting: see `docs/troubleshooting.md`.",
        "- ROHub upload + SPARQL queries: see `notebooks/RoCrate.ipynb`.",
        "- The original Docker-runnable build (bit-exact baseline):",
        "  [`hele-shaw-cells-runnable`](https://github.com/Simulation-Benchmarks/hele-shaw-cells-example/blob/main/docs/hele-shaw-cells.md#relationship-to-hele-shaw-cells-runnable).",
    ))

    cells.append(code(
        "import os, subprocess, time, json, sys",
        "from pathlib import Path",
        "",
        "# ---- Configuration: set these before running the heavy cells ----",
        "#",
        "# RUN_SIMULATION: 1 = run the simulation; 0 = skip the heavy cells",
        "#                 (useful on slow machines — the math + workflow +",
        "#                  visualization skeleton still work).",
        "# CONFIGURATIONS: space-separated list of configuration IDs to run.",
        "#                 '1' = reference (fastest); '1 2 3' = full sweep.",
        "os.environ.setdefault(\"RUN_SIMULATION\", \"1\")",
        "os.environ.setdefault(\"CONFIGURATIONS\", \"1 2 3\")",
        "",
        "REPO_URL = \"https://github.com/Simulation-Benchmarks/hele-shaw-cells-example.git\"",
        "BRANCH = \"main\"",
        "REPO_DIR = \"hele-shaw-cells-example\"",
        "",
        "# Heuristics: are we already inside the repo root? If so, stay.",
        "# Markers are the unique top-level paths that distinguish the repo",
        "# from a generic directory.",
        "REPO_ROOT_MARKERS = [",
        "    \"parameters_1.json\",",
        "    \"openfoam/case_template/\",",
        "    \".github/workflows/run-benchmark.yml\",",
        "]",
        "",
        "def looks_like_repo_root(p):",
        "    return all((p / m).exists() for m in REPO_ROOT_MARKERS)",
        "",
        "# A directory with the markers could still be a stale nested clone",
        "# from a previous run. Verify by checking that the git origin",
        "# matches the expected URL.",
        "def origin_matches(candidate, expected_url):",
        "    r = subprocess.run(",
        "        [\"git\", \"-C\", str(candidate), \"config\", \"--get\", \"remote.origin.url\"],",
        "        capture_output=True, text=True, check=False,",
        "    )",
        "    if r.returncode != 0:",
        "        return False",
        "    actual = r.stdout.strip()",
        "    # Accept both https and ssh forms of the same repo.",
        "    ssh = expected_url.replace(\"https://github.com/\", \"git@github.com:\").rstrip(\".git\") + \".git\"",
        "    return actual in (expected_url, expected_url.rstrip(\".git\"), ssh)",
        "",
        "# Resolve the actual repo root. Walk up from the kernel's cwd if",
        "# necessary, so the cell works whether Jupyter was launched from",
        "# the repo root OR from a subdirectory (e.g. `notebooks/` when",
        "# nbconvert is invoked relative to the input path).",
        "def find_repo_root(start):",
        "    p = start.resolve()",
        "    # First, find all candidate roots by walking up. Then, if there",
        "    # are multiple candidates (e.g. a stale nested clone inside a",
        "    # fresh checkout), prefer the OUTERMOST one. The outermost is",
        "    # the real repo; the inner is a stale artifact.",
        "    candidates = []",
        "    for candidate in [p, *p.parents]:",
        "        if looks_like_repo_root(candidate) and origin_matches(candidate, REPO_URL):",
        "            candidates.append(candidate)",
        "    if not candidates:",
        "        return None",
        "    # Outermost = the one with the longest path (i.e. closest to /)",
        "    # OR the one whose parent is also a candidate (the outermost).",
        "    # Simplest: sort by string length descending, take the longest.",
        "    return max(candidates, key=lambda c: len(str(c)))",
        "",
        "cwd = Path.cwd()",
        "root = find_repo_root(cwd)",
        "if root is not None:",
        "    if root != cwd:",
        "        os.chdir(root)",
        "        print(f\"Found the repo at {root}; entered it.\")",
        "    else:",
        "        print(f\"Already inside the repo at {root}; using it directly.\")",
        "else:",
        "    # No existing clone with a matching origin. Clone into the",
        "    # kernel's cwd (NOT into a notebooks/ subdirectory) and enter it.",
        "    print(f\"Cloning {REPO_URL} (branch {BRANCH}) into {cwd / REPO_DIR} ...\")",
        "    subprocess.run([\"git\", \"clone\", \"--depth\", \"1\", \"-b\", BRANCH, REPO_URL, REPO_DIR], check=True)",
        "    os.chdir(REPO_DIR)",
        "",
        "# Show the user where we are and the latest commits.",
        "print(f\"\\nNow in: {Path.cwd()}\")",
        "print(\"Latest 5 commits:\")",
        "subprocess.run([\"git\", \"log\", \"--oneline\", \"-n\", \"5\"])",
    ))

    # ============================================================
    # Section 2: Build the Docker image (cells 3-4)
    # ============================================================
    cells.append(md(
        "## Build the OpenFOAM Docker image",
        "",
        "The image is built on top of `opencfd/openfoam-default:2112` —",
        "the official OpenCFD image with OpenFOAM-v2112 pre-built. We add",
        "a 30-second `wmake` of our custom `heleShawFoam` solver on top.",
        "",
        "Image size on disk: **1.83 GB** (vs ~6.6 GB for a from-source OF",
        "build). Compressed: ~400 MB.",
        "",
        "The `Dockerfile` is at `openfoam/Dockerfile`. It is a single-stage",
        "build; the build context is the `openfoam/` directory.",
    ))

    cells.append(code(
        "import time",
        "# Read RUN_SIMULATION directly from the env (this cell runs before the",
        "# cell that defines RUN_SIM).",
        "RUN_SIM = os.environ.get(\"RUN_SIMULATION\", \"1\") == \"1\"",
        "if not RUN_SIM:",
        "    print(\"RUN_SIMULATION=0; skipping the Docker build.\")",
        "    print(\"If you want to run the simulation, set RUN_SIMULATION=1\")",
        "    print(\"in the cell at the top of this notebook and re-run from here.\")",
        "    print()",
        "    print(\"Verifying that the image exists (cached from a prior run):\")",
        "    r = subprocess.run([\"docker\", \"images\", \"hele-shaw\"], capture_output=True, text=True)",
        "    print(r.stdout or r.stderr)",
        "else:",
        "    t0 = time.monotonic()",
        "    print(\"Building the hele-shaw image (this will take a few minutes on a fresh pull)...\")",
        "    # Three invocation styles, in order of preference:",
        "    #  1. `docker buildx build --load` — modern Docker with the",
        "    #     buildx component (>= Docker 23.0+ with buildx installed).",
        "    #  2. `docker build` — legacy path; emits a deprecation warning on",
        "    #     modern Docker, but works on any version.",
        "    # We try (1) first, then (2) if (1) fails with 'unknown flag'",
        "    # (which means the user's Docker lacks the buildx component).",
        "    build_cmd = None",
        "    last_err = None",
        "    for candidate in ([",
        "        [\"docker\", \"buildx\", \"build\", \"--load\", \"-t\", \"hele-shaw:latest\", \"openfoam/\"],",
        "        [\"docker\", \"build\", \"-t\", \"hele-shaw:latest\", \"openfoam/\"],",
        "    ]):",
        "        r = subprocess.run(candidate, capture_output=True, text=True)",
        "        last_err = r",
        "        if r.returncode == 0:",
        "            build_cmd = candidate",
        "            print(r.stdout)",
        "            break",
        "        if \"unknown flag\" in r.stderr or \"unknown command\" in r.stderr:",
        "            print(f\"  (skipping: {' '.join(candidate[1:3])} not supported)\")",
        "            continue",
        "        # Some other failure (e.g. daemon down) — surface and stop.",
        "        print(r.stdout)",
        "        print(r.stderr, file=__import__('sys').stderr)",
        "        print()",
        "        print(f\"docker build failed (rc={r.returncode}). Common causes:\")",
        "        print(\"  - Colima not started: 'colima start'\")",
        "        print(\"  - Docker daemon down: 'docker ps' to verify\")",
        "        print(\"  - Pull throttled: re-run the cell after a few minutes\")",
        "        raise subprocess.CalledProcessError(r.returncode, candidate, r.stderr)",
        "    if build_cmd is None:",
        "        # Both buildx and legacy build were rejected as 'unknown'.",
        "        if last_err is not None:",
        "            print(last_err.stdout)",
        "            print(last_err.stderr, file=__import__('sys').stderr)",
        "        raise RuntimeError(",
        "            \"Could not find a working 'docker build' invocation. \"",
        "            \"Install the buildx component or upgrade to Docker 23+.\"",
        "        )",
        "    elapsed = time.monotonic() - t0",
        "    print(f\"\\nBuild completed in {elapsed:.0f} s via: {' '.join(build_cmd[1:3])}\")",
        "    subprocess.run([\"docker\", \"images\", \"hele-shaw\"])",
    ))

    # ============================================================
    # Section 3: Mathematical model (cells 5-12)
    # ============================================================
    cells.append(md(
        "## Mathematical model",
        "",
        "The full math is in [`docs/hele-shaw-cells.md`](docs/hele-shaw-cells.md).",
        "The summary below covers what you need to *interpret* the simulation",
        "results. MathJax rendering is on by default in Jupyter, so the",
        "LaTeX below renders as equations.",
    ))

    cells.append(md(
        "### Governing equations in the gap",
        "",
        "We model incompressible two-phase flow in a thin gap $b \\ll R$ between",
        "two parallel circular plates. The governing equations are:",
        "",
        "$$\\nabla \\cdot \\mathbf{u} = 0$$",
        "",
        "$$\\rho \\left(\\frac{\\partial \\mathbf{u}}{\\partial t} + \\mathbf{u} \\cdot \\nabla \\mathbf{u}\\right) = -\\nabla p + \\nabla \\cdot (2\\mu \\mathbf{D}) + \\mathbf{f}_{\\sigma}$$",
        "",
        "with $\\mathbf{D} = \\frac{1}{2}(\\nabla \\mathbf{u} + \\nabla \\mathbf{u}^\\top)$.",
        "The volume fraction $\\alpha \\in [0, 1]$ (1 = pure air, 0 = pure soap)",
        "is advected by:",
        "",
        "$$\\frac{\\partial \\alpha}{\\partial t} + \\nabla \\cdot (\\alpha \\mathbf{u}) = 0$$",
        "",
        "with the `isoAdvector` scheme adding a sharp-interface compression",
        "term. Surface tension is captured via the Continuum Surface Force",
        "(CSF) model:",
        "",
        "$$\\mathbf{f}_{\\sigma} = \\sigma \\kappa \\nabla \\alpha, \\qquad \\kappa = \\nabla \\cdot \\left(\\frac{\\nabla \\alpha}{|\\nabla \\alpha|}\\right)$$",
    ))

    cells.append(md(
        "### Gap-averaged 2D model",
        "",
        "For Newtonian flow with no-slip on both plates, averaging across the",
        "gap gives a Darcy-like 2D form:",
        "",
        "$$\\langle \\mathbf{u} \\rangle = -\\frac{b^2}{12\\mu} \\nabla p$$",
        "",
        "with $\\nabla \\cdot \\langle \\mathbf{u} \\rangle = Q / (\\pi R_\\text{in}^2)$",
        "at the inlet. The `heleShawFoam` solver implements the **un-averaged**",
        "(full 3D-in-z) form with a single cell in the z-direction (`NPB = 1`)",
        "and a `gapWidth` parameter, so the result is equivalent to the averaged",
        "model up to discretization error.",
    ))

    cells.append(md(
        "### Initial and boundary conditions",
        "",
        "**Geometry**:",
        "",
        "- $R_\\text{in} = 1.5$ mm, $R_\\text{out} = 95$ mm, $b = 1$ mm.",
        "- 2D axisymmetric, single cell in z-direction (a gap of height $b$).",
        "",
        "**Initial condition**:",
        "",
        "- `alpha.air` is uniform 0 (no air anywhere).",
        "- `setFields` (in `system/setFieldsDict`) sets `alpha.air = 1` inside a",
        "  small cylinder (radius 2.5 mm, height 2.4 mm) at the centre, which",
        "  is the initial air bubble.",
        "",
        "**Boundary conditions**:",
        "",
        "- `inlet` (at $R = R_\\text{in}$): `flowRateInletVelocity` with",
        "  prescribed volumetric flow rate $Q$ (the parameter we sweep).",
        "- `outlet` (at $R = R_\\text{out}$): `inletOutlet`, allowing outflow.",
        "- `plates` (at $z = \\pm b/2$): `fixedValue` (no-slip).",
        "",
        "**Fluid properties** (from `constant/transportProperties`):",
        "",
        "| Phase | ρ (kg/m³) | k (m²/s) | n (-) |",
        "|---|---|---|---|",
        "| air  | 1.2     | 1.5×10⁻⁵ | 1.0 |",
        "| soap | 1026.6  | 2.0×10⁻³ | 1.0 |",
        "",
        "Surface tension coefficient: $\\sigma = 0.031$ N/m.",
        "",
        "Both phases use the `powerLaw` transport model with $n=1$ (Newtonian).",
    ))

    cells.append(md(
        "### Dimensionless numbers",
        "",
        "Four dimensionless numbers govern the pattern:",
        "",
        "- **Capillary number** $\\mathrm{Ca} = \\mu_\\text{soap} U / \\sigma$ —",
        "  ratio of viscous forces to surface tension. Small $\\mathrm{Ca}$ means",
        "  surface tension dominates and the fingers are highly branched.",
        "- **Viscosity ratio** $M = \\mu_\\text{air} / \\mu_\\text{soap}$ —",
        "  ratio of the displaced fluid's viscosity to the displacing fluid's.",
        "  For the air-soap system, $M \\ll 1$ (unfavourable viscosity ratio,",
        "  which is why fingering happens at all).",
        "- **Reynolds number** $\\mathrm{Re} = \\rho U b / \\mu$ —",
        "  ratio of inertial to viscous forces. In this gap, $\\mathrm{Re} \\ll 1$:",
        "  viscous (Stokes) flow, no inertia.",
        "- **Péclet-like** $\\mathrm{Pe} = Q / (D_\\alpha R_\\text{in})$ —",
        "  ratio of advection to interface diffusion. Here advection wins by",
        "  many orders of magnitude.",
    ))

    cells.append(code(
        "# Compute the dimensionless numbers for the reference config.",
        "Q = 4.0e-7          # m^3/s, reference inlet volumetric flow rate",
        "R_in = 1.5e-3       # m, inlet radius",
        "b = 1.0e-3          # m, gap height",
        "rho_soap = 1026.6   # kg/m^3, soap density",
        "mu_soap = 2.0e-3    # Pa.s, soap dynamic viscosity (with n=1, k=mu)",
        "mu_air = 1.5e-5     # Pa.s, air dynamic viscosity (with n=1, k=mu)",
        "sigma = 0.031       # N/m, surface tension coefficient",
        "",
        "import math",
        "# The inlet is an annular slot at R=R_in with height b. The gap-",
        "# averaged velocity at the inlet is Q / (2 pi R_in b).",
        "U_inlet = Q / (2 * math.pi * R_in * b)",
        "Ca = mu_soap * U_inlet / sigma",
        "M = mu_air / mu_soap",
        "Re_soap = rho_soap * U_inlet * b / mu_soap",
        "Re_air = 1.2 * U_inlet * b / mu_air",
        "",
        "print(f\"Inlet gap-averaged velocity:  U = {U_inlet:.4f} m/s\")",
        "print(f\"Capillary number (soap):     Ca = {Ca:.4f}\")",
        "print(f\"Viscosity ratio (air/soap):  M  = {M:.5f}\")",
        "print(f\"Reynolds number (soap):      Re = {Re_soap:.4f}\")",
        "print(f\"Reynolds number (air):       Re = {Re_air:.4f}\")",
        "print()",
        "print(\"Interpretation:\")",
        "print(f\"  - Ca << 1: surface tension dominates -> fingers are highly branched.\")",
        "print(f\"  - M << 1: viscosity ratio is very unfavourable (Saffman-Taylor unstable).\")",
        "print(f\"  - Re << 1: viscous (Stokes) flow, no inertia.\")",
    ))

    cells.append(md(
        "### Reference result",
        "",
        "A reference result, extracted from the runnable repo's verified run at",
        "$t \\approx 10$ s, is shown below. The air bubble has grown from its",
        "initial 2.5-mm radius and developed radial fingers as it displaced the",
        "more viscous soap. The pattern is mesh-dependent at this resolution;",
        "the bulk statistics (number of fingers, mean tip radius) are",
        "qualitatively similar across runs.",
        "",
        "![Hele-Shaw viscous fingering at t~=10s](docs/hele-shaw-cells.png)",
        "",
        "The full image with all 301 time-step frames is available in the",
        "runnable repo's `testcase/Results/sim_*.avi` (ParaView-readable).",
    ))

    cells.append(md(
        "### Solver numerics",
        "",
        "The custom solver `heleShawFoam` is based on `interFoam` (the canonical",
        "VOF solver in OpenFOAM) with the `gapWidth` parameter replacing the",
        "third spatial dimension. The interface-capture scheme is `isoAdvector`",
        "(Roenby, Eijkhout, 2016), which gives sharper interfaces than the",
        "default `MULES` limiter.",
        "",
        "Solver settings (from `system/controlDict`):",
        "",
        "- `endTime = 15` s",
        "- `deltaT = 0.1` s (initial; adaptive via `adjustTimeStep`)",
        "- `writeInterval = 0.05` s → 301 output frames",
        "- `maxCo = 0.5`, `maxAlphaCo = 0.5` (CFL constraints)",
        "",
        "The full discretization strategy is in `docs/hele-shaw-cells.md`",
        "§Discretization strategy.",
    ))

    cells.append(code(
        "# Sanity check: load the reference parameters and print them structured.",
        "params_1 = json.loads(Path(\"parameters_1.json\").read_text())",
        "print(\"Reference configuration (parameters_1.json):\")",
        "print(json.dumps(params_1, indent=2))",
    ))

    # ============================================================
    # Section 4: Configurations (cells 13-15)
    # ============================================================
    cells.append(md(
        "## The parameter sweep",
        "",
        "This benchmark ships with three configurations that probe different",
        "aspects of the simulation:",
        "",
        "- **Configuration 1** — the reference. $NPA = NPZ = 60$ (14400 cells),",
        "  $Q = 4 \\times 10^{-7}$ m³/s. Wall time: ~3-5 min on native amd64.",
        "- **Configuration 2** — mild mesh refinement. Same $Q$, but $NPA = NPZ = 80$",
        "  (6400 cells). Lets you see how the metric changes with mesh",
        "  discretisation.",
        "- **Configuration 3** — flow-rate variation. Same mesh as config 1, but",
        "  $Q = 8 \\times 10^{-7}$ m³/s (twice the default). Lets you see how the",
        "  metric changes with the inlet flow rate.",
        "",
        "By default, the notebook runs all three. To run only config 1 (the",
        "fastest end-to-end check), set `CONFIGURATIONS = \"1\"` in the cell",
        "at the top of this notebook (or in your environment).",
    ))

    cells.append(code(
        "# Show the parameter sweep as a pandas DataFrame.",
        "import pandas as pd",
        "",
        "rows = []",
        "for p in sorted(Path(\".\").glob(\"parameters_*.json\")):",
        "    cfg = p.stem.split(\"_\", 1)[1]",
        "    data = json.loads(p.read_text())",
        "    rows.append({",
        "        \"configuration\": cfg,",
        "        \"NPA\": data[\"mesh\"][\"NPA\"],",
        "        \"NPZ\": data[\"mesh\"][\"NPZ\"],",
        "        \"NPB\": data[\"mesh\"][\"NPB\"],",
        "        \"inlet_flow_rate_m3_s\": data[\"boundary_conditions\"][\"inlet_volumetric_flow_rate\"],",
        "        \"endTime_s\": data[\"solver\"][\"endTime\"],",
        "        \"bubble_radius_m\": data[\"initial_condition\"][\"bubble_radius\"],",
        "    })",
        "sweep = pd.DataFrame(rows).set_index(\"configuration\") if rows else pd.DataFrame()",
        "sweep",
    ))

    cells.append(md(
        "**What each config probes**",
        "",
        "- Compare configurations 1 and 2: they share the same flow rate but",
        "  differ in mesh resolution. Any difference in `phase1_volume_fraction`",
        "  is mesh-discretisation error.",
        "- Compare configurations 1 and 3: they share the same mesh but differ",
        "  in flow rate. The doubling of $Q$ should give a visibly higher",
        "  air volume fraction at endTime (more air injected = more air in the",
        "  cell).",
        "- Comparing all three at once is a small 2×2 design with the mesh as",
        "  one factor and the flow rate as the other.",
    ))

    # ============================================================
    # Section 5: Run (cells 16-21)
    # ============================================================
    cells.append(md(
        "## Run the simulation",
        "",
        "The simulation is orchestrated by `openfoam/run_benchmark.py`, which",
        "for each configuration:",
        "",
        "1. Renders the case templates (Jinja2) using the parameter JSON.",
        "2. Generates the mesh via `create_mesh.py` (a wrapper around",
        "   `circulardomain.py` + `docker run hele-shaw blockMesh`).",
        "3. Runs the simulation via `docker run hele-shaw:latest` (or",
        "   `Allrun` natively with `--native`).",
        "4. Post-processes the log and alpha field to compute the five",
        "   metrics and write `solution_metrics.json`.",
        "5. Packages the run's time-step directories and the rendered OF",
        "   dictionaries into `solution_field_data.zip` (with a",
        "   hand-rolled RO-Crate metadata file).",
        "",
        "On native amd64, expect ~3-5 minutes per configuration. On",
        "QEMU-emulated arm64, ~15-20 minutes per configuration.",
    ))

    cells.append(code(
        "# Pick which configurations to run. Override at the top of the notebook",
        "# by editing os.environ[\"CONFIGURATIONS\"], or set the env var before",
        "# launching Jupyter: CONFIGURATIONS=\"1\" jupyter lab ...",
        "CONFIGS = os.environ[\"CONFIGURATIONS\"].split()",
        "print(f\"Will run {len(CONFIGS)} configuration(s): {CONFIGS}\")",
        "",
        "# If you want to skip the simulation entirely (e.g. on a slow machine),",
        "# set RUN_SIMULATION=0 in the environment. The math + workflow + viz",
        "# skeleton still works.",
        "RUN_SIM = os.environ.get(\"RUN_SIMULATION\", \"1\") == \"1\"",
        "print(f\"RUN_SIMULATION = {RUN_SIM}\")",
    ))

    cells.append(code(
        "# Generate the workflow config and ensure each config has a mesh tarball.",
        "if RUN_SIM:",
        "    try:",
        "        subprocess.run([\"python\", \"generate_config.py\"], check=True)",
        "        print()",
        "        for cfg in CONFIGS:",
        "            if not Path(f\"mesh_{cfg}.tar.gz\").exists():",
        "                print(f\"Creating mesh for configuration {cfg}...\")",
        "                t0 = time.monotonic()",
        "                # create_mesh.py calls 'docker run hele-shaw blockMesh'",
        "                # internally. If the Docker daemon is down, it will fail",
        "                # with FileNotFoundError or CalledProcessError; we",
        "                # surface the message and stop the loop.",
        "                subprocess.run([\"python\", \"create_mesh.py\", cfg], check=True)",
        "                print(f\"  mesh_{cfg}.tar.gz created in {time.monotonic() - t0:.1f} s\")",
        "            else:",
        "                print(f\"Reusing existing mesh_{cfg}.tar.gz\")",
        "    except (subprocess.CalledProcessError, FileNotFoundError) as e:",
        "        print(f\"Mesh generation failed: {e}\")",
        "        print(\"Common causes:\")",
        "        print(\"  - Colima not started: 'colima start'\")",
        "        print(\"  - Docker daemon down: 'docker ps' to verify\")",
        "        print(\"  - Missing image: re-run the build cell above\")",
        "        raise",
        "else:",
        "    print(\"RUN_SIMULATION=0; skipping config generation and mesh creation.\")",
    ))

    cells.append(code(
        "# The heavy lift: run the simulation for each configuration.",
        "if RUN_SIM:",
        "    overall_t0 = time.monotonic()",
        "    for cfg in CONFIGS:",
        "        print(f\"\\n{'='*70}\")",
        "        print(f\"=== Running configuration {cfg} ===\")",
        "        print(f\"{'='*70}\")",
        "        cfg_t0 = time.monotonic()",
        "        try:",
        "            subprocess.run([",
        "                \"python\", \"openfoam/run_benchmark.py\",",
        "                \"--no-snakemake\",",
        "                \"--configurations\", cfg,",
        "                \"--docker-image\", \"hele-shaw:latest\",",
        "            ], check=True)",
        "        except (subprocess.CalledProcessError, FileNotFoundError) as e:",
        "            print(f\"\\nConfiguration {cfg} FAILED: {e}\")",
        "            print(\"Check:\")",
        "            print(\"  - The Docker image is built (re-run the build cell)\")",
        "            print(\"  - The Colima/Docker daemon is running\")",
        "            print(f\"  - The mesh_{cfg}.tar.gz exists (re-run the previous cell)\")",
        "            raise",
        "        print(f\"\\nConfiguration {cfg} done in {time.monotonic() - cfg_t0:.0f} s\")",
        "    print(f\"\\nTotal wall time: {time.monotonic() - overall_t0:.0f} s\")",
        "else:",
        "    print(\"RUN_SIMULATION=0; skipping the simulation.\")",
    ))

    cells.append(md(
        "**What just happened** (during `run_benchmark.py`):",
        "",
        "- The OF dictionaries (`0/U`, `0/alpha.air`, `0/p_rgh`,",
        "  `constant/transportProperties`, `system/controlDict`,",
        "  `system/setFieldsDict`) were rendered from the parameter JSON.",
        "- The mesh tarball was untarred into `constant/polyMesh/`.",
        "- `docker run --rm -v $PWD/results/<cfg>:/case hele-shaw:latest` was",
        "  executed, which sourced the OF environment and ran `./Allrun`.",
        "- The post-processing parsed the OF log for the cumulative continuity",
        "  error, the solver-reported phase-1 volume fraction, and the wall",
        "  time. The alpha field at t=15 was parsed for the interface",
        "  length proxy (cells with $0 < \\alpha < 1$).",
        "- `solution_metrics.json` and `solution_field_data.zip` (with the",
        "  m4i:-augmented `ro-crate-metadata.json`) were written.",
    ))

    cells.append(code(
        "# Optional: aggregate the per-config metrics into a summary table.",
        "if RUN_SIM and len(CONFIGS) > 1:",
        "    metric_files = [str(Path(\"results\") / cfg / \"solution_metrics.json\") for cfg in CONFIGS]",
        "    try:",
        "        subprocess.run([",
        "            \"python\", \"openfoam/summarize_results.py\",",
        "            *metric_files,",
        "            \"--output\", \"results/summary.json\",",
        "        ], check=True)",
        "    except (subprocess.CalledProcessError, FileNotFoundError) as e:",
        "        print(f\"summarize_results.py failed: {e}\")",
        "        print(\"Continuing without the aggregated table.\")",
        "    if os.environ.get(\"PLOT\", \"1\") == \"1\":",
        "        try:",
        "            subprocess.run([",
        "                \"python\", \"openfoam/summarize_metrics.py\",",
        "                \"--summary-csv\", \"results/summary.csv\",",
        "                \"--output-dir\", \"results\",",
        "            ], check=True)",
        "        except (subprocess.CalledProcessError, FileNotFoundError) as e:",
        "            print(f\"Plot generation failed (matplotlib missing?): {e}\")",
        "elif RUN_SIM:",
        "    print(\"Only one configuration; skipping aggregation step.\")",
        "else:",
        "    print(\"RUN_SIMULATION=0; skipping aggregation step.\")",
    ))

    # ============================================================
    # Section 6: Inspect results (cells 22-30)
    # ============================================================
    cells.append(md(
        "## Inspect the results",
        "",
        "The simulation produces:",
        "",
        "- `results/<config>/solution_metrics.json` — the five metrics per",
        "  configuration (phase1_volume_fraction, cumulative_continuity_error,",
        "  interface_length_proxy, wall_time_seconds, time_step_count).",
        "- `results/<config>/solution_field_data.zip` — the time-step dirs, the",
        "  log, the rendered OF dicts, and the m4i:-augmented RO-Crate metadata.",
        "- `results/<config>/fingers.png` — the post-run alpha-field plot",
        "  (generated by `openfoam/plot_fingers.py` below).",
        "- `results/summary.json` / `results/summary.csv` — the aggregated table",
        "  (only if you ran more than one configuration).",
        "- `results/phase1_volume_fraction_vs_*.pdf` — the sweep plots",
        "  (also only if you ran more than one configuration).",
    ))

    cells.append(code(
        "# Read the metrics for each configuration and tabulate them.",
        "import pandas as pd",
        "",
        "rows = []",
        "for cfg in CONFIGS:",
        "    metrics_path = Path(\"results\") / cfg / \"solution_metrics.json\"",
        "    if not metrics_path.exists():",
        "        print(f\"Skipping {cfg}: {metrics_path} not found\")",
        "        continue",
        "    m = json.loads(metrics_path.read_text())[\"metrics\"]",
        "    rows.append({",
        "        \"configuration\": cfg,",
        "        \"phase1_volume_fraction\": m.get(\"phase1_volume_fraction\"),",
        "        \"cumulative_continuity_error\": m.get(\"cumulative_continuity_error\"),",
        "        \"interface_length_proxy\": m.get(\"interface_length_proxy\"),",
        "        \"wall_time_seconds\": m.get(\"wall_time_seconds\"),",
        "        \"time_step_count\": m.get(\"time_step_count\"),",
        "    })",
        "metrics_df = pd.DataFrame(rows).set_index(\"configuration\") if rows else pd.DataFrame()",
        "metrics_df",
    ))

    cells.append(code(
        "# Smoke-test the metrics against the saved baselines.",
        "# This will fail (loudly) if any metric is out of tolerance.",
        "if RUN_SIM:",
        "    for cfg in CONFIGS:",
        "        metrics_path = Path(\"results\") / cfg / \"solution_metrics.json\"",
        "        if not metrics_path.exists():",
        "            continue",
        "        print(f\"\\n=== Smoke test: configuration {cfg} ===\")",
        "        result = subprocess.run([",
        "            \"python\", \"tests/compare.py\",",
        "            str(metrics_path),",
        "            \"tests/baseline/metrics_baseline.json\",",
        "            \"--tol-json\", \"tests/baseline/metrics_tolerances.json\",",
        "        ])",
        "        # NOTE: tests/compare.py exits with 1 if any metric is out of",
        "        # tolerance. That's a real change in the simulation, not a",
        "        # bug. The baseline is for the reference config; configs 2 and 3",
        "        # will legitimately differ.",
        "else:",
        "    print(\"RUN_SIMULATION=0; skipping the smoke test.\")",
    ))

    cells.append(md(
        "### The fingers — a picture is worth a thousand numbers",
        "",
        "The next two cells generate a multi-panel image of the alpha field",
        "at several time points, and embed it in this notebook. The image",
        "is also saved to `results/<config>/fingers.png`.",
    ))

    cells.append(code(
        "# Generate the fingers plot for each configuration and embed it.",
        "if RUN_SIM:",
        "    from IPython.display import Image, display",
        "    for cfg in CONFIGS:",
        "        out = Path(\"results\") / cfg / \"fingers.png\"",
        "        try:",
        "            subprocess.run([",
        "                \"python\", \"openfoam/plot_fingers.py\",",
        "                \"--results-dir\", f\"results/{cfg}\",",
        "                \"--times\", \"0.05\", \"1\", \"5\", \"10\", \"15\",",
        "                \"--output\", str(out),",
        "            ], check=True)",
        "            print(f\"\\n--- Configuration {cfg} ---\")",
        "            display(Image(filename=str(out)))",
        "        except subprocess.CalledProcessError as e:",
        "            print(f\"plot_fingers.py failed for {cfg}: {e}\")",
        "else:",
        "    print(\"RUN_SIMULATION=0; skipping the fingers plot.\")",
    ))

    cells.append(code(
        "# Inspect the alpha field at t=15 directly: cell count, air-cell count,",
        "# interface-cell count. Sanity-check that the parser is working.",
        "import sys",
        "sys.path.insert(0, \"openfoam\")",
        "from metrics import parse_alpha_field  # type: ignore[import-not-found]",
        "",
        "if RUN_SIM:",
        "    for cfg in CONFIGS:",
        "        alpha_path = Path(\"results\") / cfg / \"15\" / \"alpha.air\"",
        "        if not alpha_path.exists():",
        "            print(f\"Skipping {cfg}: {alpha_path} not found\")",
        "            continue",
        "        s = parse_alpha_field(str(alpha_path))",
        "        if s is None:",
        "            print(f\"Configuration {cfg}: alpha field is uniform; skipping\")",
        "            continue",
        "        print(f\"Configuration {cfg} at t=15:\")",
        "        print(f\"  total cells:     {s['n_cells']}\")",
        "        print(f\"  air cells:       {s['n_air_cells']}\")",
        "        print(f\"  interface cells: {s['n_interface_cells']}\")",
        "        print(f\"  cell-fraction air: {s['phase1_volume_fraction']:.4f}\")",
        "        print()",
        "else:",
        "    print(\"RUN_SIMULATION=0; skipping the alpha field inspection.\")",
    ))

    cells.append(md(
        "**Note on `phase1_volume_fraction`**: the value reported in",
        "`solution_metrics.json` is the *solver-reported* phase-1 volume",
        "fraction (an integral of $\\alpha$ over the cell volumes), not the",
        "cell-fraction-with-$\\alpha > 0.5$ we just computed. The two are",
        "different because `isoAdvector`'s compression step smears the",
        "interface over ~3 cells. The solver-reported value is the ground",
        "truth; the cell fraction is a sanity check.",
    ))

    cells.append(md(
        "### Compare to the runnable repo's reference",
        "",
        "The reference Docker-runnable build",
        "([`hele-shaw-cells-runnable`](https://github.com/Simulation-Benchmarks/hele-shaw-cells-example))",
        "stores a bit-exact baseline in `tests/baseline/`. If you ran the",
        "notebook on the same hardware with the same Docker image, your",
        "`phase1_volume_fraction` at endTime should match to within `~0.01`",
        "and the alpha field at t=15 should be bit-exact (`L_\\infty = 0`).",
        "",
        "If you ran on different hardware (especially under QEMU emulation),",
        "the bit-exact match will not hold, but the bulk statistics (air",
        "volume fraction, number of fingers) will be qualitatively similar.",
    ))

    cells.append(code(
        "# Peek at the m4i-augmented RO-Crate inside one of the solution_field_data.zip",
        "# files. This is the provenance the platform's SPARQL queries walk.",
        "import tarfile",
        "",
        "if RUN_SIM:",
        "    sample_zip = Path(\"results\") / CONFIGS[0] / \"solution_field_data.zip\"",
        "    if not sample_zip.exists():",
        "        print(f\"{sample_zip} not found; skipping the RO-Crate peek\")",
        "    else:",
        "        with tarfile.open(sample_zip, \"r:gz\") as tf:",
        "            for member in tf.getmembers():",
        "                if member.name == \"ro-crate-metadata.json\":",
        "                    crate = json.loads(tf.extractfile(member).read())",
        "                    break",
        "        # Find the m4i:Method node.",
        "        m4i_method = None",
        "        for node in crate[\"@graph\"]:",
        "            t = node.get(\"@type\", \"\")",
        "            if \"metadata4ing\" in t and \"Method\" in t:",
        "                m4i_method = node",
        "                break",
        "        if m4i_method is None:",
        "            print(\"No m4i:Method node found in the RO-Crate.\")",
        "        else:",
        "            print(\"m4i:Method node:\")",
        "            print(json.dumps(m4i_method, indent=2)[:1200])",
        "            print(\"...\")",
        "else:",
        "    print(\"RUN_SIMULATION=0; skipping the RO-Crate peek.\")",
    ))

    cells.append(md(
        "## Where to go from here",
        "",
        "- **Cross-benchmark SPARQL queries** — see `notebooks/RoCrate.ipynb`",
        "  for the ROHub upload + SPARQL flow. The m4i:-augmented RO-Crate you",
        "  just peeked at is the input to that notebook.",
        "- **Troubleshooting** — see `docs/troubleshooting.md` if the simulation",
        "  crashes or the smoke test fails.",
        "- **Add a configuration** — copy `parameters_1.json` to",
        "  `parameters_4.json`, edit it, and re-run the notebook. The workflow",
        "  will pick it up automatically.",
        "- **Add a tool** — drop a new folder under `openfoam/` (or a new top-",
        "  level folder for a non-OF solver), implement the blueprint's",
        "  `--input-parameter-file --input-mesh-file --output-solution-file-zip",
        "  --output-metrics-file` arg contract, and update `generate_config.py`'s",
        "  `--tools` list. See the platform's `benchmark_addition_guide.md`.",
    ))

    return cells


def main() -> int:
    nb = {
        "cells": build_cells(),
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": sys.version.split()[0],
                "mimetype": "text/x-python",
                "codemirror_mode": {"name": "ipython", "version": 3},
                "pygments_lexer": "ipython3",
                "nbconvert_exporter": "python",
                "file_extension": ".py",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(nb, indent=1))
    print(f"wrote {OUT}  ({len(nb['cells'])} cells)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
