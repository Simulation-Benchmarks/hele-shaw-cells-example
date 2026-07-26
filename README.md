# Hele-Shaw Cells Example

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20728189.svg)](https://doi.org/10.5281/zenodo.20728189)

A blueprint-aligned instance repository for the **Hele-Shaw cells** benchmark
from the [NFDI4IngModelValidationPlatform](https://github.com/Simulation-Benchmarks/NFDI4IngModelValidationPlatform).

This repository contains the same 2D OpenFOAM simulation of **radial viscous
fingering in a circular Hele-Shaw cell** as
[`hele-shaw-cells-runnable`](../hele-shaw-cells-runnable), restructured
to fit the [instance-repo schema](../NFDI4IngModelValidationPlatform/docs/getting_started/benchmark_addition_guide.md).
The Docker image, solver, mesh, fluid properties, and numerics are
**identical**; only the repository layout follows the platform convention.

- **Problem definition**: [docs/hele-shaw-cells.md](docs/hele-shaw-cells.md)
- **Troubleshooting**: [docs/troubleshooting.md](docs/troubleshooting.md)
- **Install guide (macOS / Linux / WSL2 / remote VMs)**: [docs/getting_started.md](docs/getting_started.md)
- **ROHub upload + SPARQL queries**: [docs/rohub.md](docs/rohub.md)
- **Walkthrough notebook** (clone → build → math → run → inspect): [notebooks/Simulation_Walkthrough.ipynb](notebooks/Simulation_Walkthrough.ipynb)
- **ROHub notebook**: [notebooks/RoCrate.ipynb](notebooks/RoCrate.ipynb)
- **Original Docker-runnable build**: [`hele-shaw-cells-runnable`](../hele-shaw-cells-runnable)
- **Original research artifact**: [`hele-shaw-cells/`](../hele-shaw-cells) (Yao Zhang, 2024)

## Quick start

The recommended path is the **walkthrough notebook**: it clones (or
detects) the repo, builds the Docker image, walks through the
mathematical model, runs the simulation, and visualises the fingers.

```bash
# 0. Install Docker (any flavour). On macOS, Colima is the lightest:
brew install colima docker
colima start          # one-time per session

# 1. Clone the repo
git clone https://github.com/Simulation-Benchmarks/hele-shaw-cells-example.git
cd hele-shaw-cells-example

# 2. Set up the workflow Python env (one-time)
mamba env create -n hs-workflow -f environment.yml
conda activate hs-workflow

# 3. Open the walkthrough notebook and run the cells
jupyter lab notebooks/Simulation_Walkthrough.ipynb
```

Inside the notebook:

- **Default mode** (`RUN_SIMULATION=1`): runs all 3 configurations.
  ~10-15 min on native amd64, ~30-60 min on Apple Silicon under QEMU.
- **Fast mode** (`RUN_SIMULATION=0`): skips Docker + simulation. Math,
  parameter sweep, and visualization skeleton still work; ~1 min.

For a step-by-step install on your platform (macOS, Linux, WSL2, Hetzner,
Oracle Cloud, Paperspace, mybinder), see
[docs/getting_started.md](docs/getting_started.md).

### Command-line alternative (skip the notebook)

If you just want to run the sweep from the terminal:

```bash
conda activate hs-workflow

# Generate the workflow config and build all 3 meshes
python generate_config.py
for cfg in 1 2 3; do
    python create_mesh.py $cfg
done

# Run all 3 configurations
cd openfoam
python run_benchmark.py
cd ..

# Inspect the results
cat results/summary.json
ls results/{1,2,3}/solution_metrics.json
ls results/{1,2,3}/fingers.png
```

## What's in this repo

```
hele-shaw-cells-example/
├── README.md                         # this file
├── LICENSE                           # MIT (with OF base-image GPL-3.0 caveat)
│
├── docs/
│   ├── hele-shaw-cells.md            # problem statement + math model
│   ├── getting_started.md            # cross-platform install guide
│   ├── troubleshooting.md            # common errors and fixes
│   ├── rohub.md                      # ROHub upload + SPARQL queries
│   └── hele-shaw-cells.png           # reference finger pattern (extracted from runnable)
│
├── parameters_1.json                 # reference config (60×60 mesh, Q=4×10⁻⁷ m³/s)
├── parameters_2.json                 # mild mesh refinement (80×80)
├── parameters_3.json                 # flow-rate variation (Q=8×10⁻⁷ m³/s)
│
├── create_mesh.py                    # top-level: parameters_*.json → mesh_*.tar.gz
├── generate_config.py                # scans parameters_*.json → workflow_config.json
├── Snakefile                         # top-level workflow
│
├── openfoam/                         # the one simulation tool
│   ├── Dockerfile, docker-compose.yml, docker-entrypoint.sh
│   ├── Snakefile                     # sub-workflow
│   ├── run_simulation.py             # the tool's arg contract
│   ├── run_benchmark.py              # the direct runner (mirrors fenics/run_benchmark.py)
│   ├── summarize_results.py          # aggregate metrics → summary.json
│   ├── summarize_metrics.py          # summary.csv → PDF plots
│   ├── metrics.py                    # log + alpha-field parser
│   ├── finger_binarise.py            # alpha-field / PNG binarisation
│   ├── finger_count_tips.py          # skeletonise + 3x3-neighbour tip rule
│   ├── finger_panel_detect.py        # auto-detect panel rectangles from PNG
│   ├── finger_pipeline.py            # end-to-end: extract_finger_metrics + render_fingers_png
│   ├── ro_crate.py                   # hand-rolled ro-crate-metadata.json writer (m4i:-aware)
│   ├── _render_templates.py          # case_template/ → working case dir
│   ├── environment_simulation.yml, environment_benchmark.yml,
│   │   environment_postprocessing.yml, environment_rohub.yml
│   ├── meshgen/circulardomain.py     # OF blockMeshDict generator
│   ├── solver/                       # heleShawFoam C++ source
│   ├── case_template/                # OF dicts as Jinja2 templates
│   │   ├── 0/{alpha.air, U, p_rgh}.template
│   │   ├── constant/{g, transportProperties, turbulenceProperties}.template
│   │   ├── system/{controlDict, setFieldsDict}.template
│   │   ├── system/{fvSchemes, fvSolution}      # verbatim (no parameters)
│   │   ├── Allrun, Allclean, case2D.foam
│   │   └── Results/sim_*.avi          # the original reference AVI
│   └── tests_docker/run_container.sh
│
├── benchmark/
│   ├── hele-shaw-cells-example.zip   # the benchmark bundle (auto-generated)
│   └── build_benchmark_zip.py        # reproducible build script
│
├── results/                          # produced at runtime; .gitignored
│                                    # each config produces a dir with:
│                                    #   Allrun, solution_metrics.json,
│                                    #   solution_field_data.zip,
│                                    #   cartesian.png, fingers.png, and
│                                    #   Timesteps/<t>/  (the OF case
│                                    #   + all 301 time-step dirs)
│
├── tests/
│   ├── compare.py                    # alpha-field diff AND metrics smoke test (7 metrics)
│   ├── test_finger_pipeline.py       # unit test for the finger pipeline
│   ├── baseline/                     # captured from a verified run
│   │   ├── alpha.air_t0.05, alpha.air_t15, log.heleShawFoam
│   │   ├── metrics_baseline.json     # the 5 reference values
│   │   └── metrics_tolerances.json
│   └── baseline_v2112_arm64/         # cross-platform comparison
│
├── environment.yml, environment_benchmarks.yml
│
├── notebooks/
│   ├── Simulation_Walkthrough.ipynb  # end-to-end walkthrough (clone → build → math → run → inspect)
│   └── RoCrate.ipynb                 # ROHub upload + SPARQL queries
│
├── scripts/
│   ├── build_walkthrough_notebook.py # reproducible builder for the walkthrough notebook
│   ├── extract_reference_frame.py    # extract docs/hele-shaw-cells.png from the runnable AVI
│   ├── inspect_run.sh                # drop into the OF container with the case mounted
│   └── regenerate_baseline.sh        # re-run config 1 and refresh the baselines (destructive)
│
├── PUBLISH.md                        # 7-step publish checklist
├── PUBLISHED.md                      # records the publish event
├── ZENODO.md                         # Zenodo DOI minting steps
│
└── .github/workflows/run-benchmark.yml
```

## What does the GitHub workflow do?

`.github/workflows/run-benchmark.yml` has **three jobs**. Two of them are
disabled for automatic push triggers (commented out, per the `Phase 26:
silence failure emails` decision); they run only on `workflow_dispatch`
(manual trigger from the GitHub Actions tab). The third runs on every
push and PR.

### Job 1: `run-benchmark` (manual trigger only, currently)

- **Triggers:** `workflow_dispatch` only.
- **Runner:** `ubuntu-latest` (native amd64, no QEMU).
- **Steps:** checkout → build Docker image → set up mambaforge → create
  workflow env → generate config → build benchmark zip (regression
  check) → run all 3 configurations → summarize + plot → smoke-test
  against the baseline → upload results as a downloadable artifact.
- **Timeout:** 60 min. Each config takes ~3-5 min, so the full sweep
  fits comfortably.
- **Output artifact:** `hele-shaw-cells-example-results` (zip
  containing `results/`, `benchmark/hele-shaw-cells-example.zip`,
  `workflow_config.json`). Download from the Actions tab.

**To re-enable automatic runs** (push / PR / schedule), uncomment the
matching entries in the `on:` block at the top of the workflow file.

### Job 2: `rohub-upload` (dormant, tag-triggered)

- **Triggers:** tag pushes only (`v*`). **Currently dormant** because
  the workflow's main trigger is `workflow_dispatch`, which doesn't
  satisfy the gate.
- **Runner:** `ubuntu-latest`.
- **Steps:** download the run-benchmark artifact → set up the `hs-rohub`
  conda env (with the editable `rohub` install) → run
  `openfoam/upload_to_rohub.py` with the dev endpoint → upload the
  resulting UUIDs as a separate artifact.
- **Soft-skip:** if `ROHUB_USERNAME` / `ROHUB_PASSWORD` secrets are not
  set, the job writes `{"skipped": true, "reason": "secrets not
  configured"}` to the UUID file and exits 0. Never fails the build.
- **To enable:** re-enable tag triggers in the `on:` block AND set the
  ROHub secrets in the repo's Settings → Secrets → Actions.

### Job 3: `notebook-smoke` (every push and PR)

- **Triggers:** every push to `main` and every PR; skipped on the daily
  schedule to save CI minutes.
- **Runner:** `ubuntu-latest`.
- **Steps:** install Jupyter deps → validate the notebook
  (`nbformat.validate`) → execute the notebook in fast mode
  (`RUN_SIMULATION=0`) → upload the executed notebook as an artifact.
- **Timeout:** 15 min.
- **Catches regressions in the notebook itself** — broken code cells,
  missing imports, etc. ~1 min wall time per run.

## Output metrics

Each configuration produces `results/<config>/solution_metrics.json`
with these seven metrics:

| Metric | Description | Typical value (config 1) |
|---|---|---|
| `phase1_volume_fraction` | Air volume fraction at endTime, as reported by the solver | ~0.21 |
| `cumulative_continuity_error` | Final cumulative mass-balance error | ~5.6×10⁻⁴ |
| `interface_length_proxy` | Cells with 0 < α < 1 (proxy for the air-cluster perimeter) | ~2141 |
| `wall_time_seconds` | OF `ExecutionTime` | depends on host |
| `time_step_count` | Number of write-time directories produced | 301 |
| `final_number_of_fingers` | Number of fingertips in the binarised final-frame alpha field (alpha > 0.5 + skeletonise + 3x3-neighbour tip rule) | ~15 |
| `critical_radius_m` | Smallest distance from the cell centre to the air region's boundary at the last time-step, in metres | ~0.016 |

The two new finger metrics are computed by the alpha-field path of
`openfoam/finger_pipeline.py:extract_finger_metrics`, which reads the
alpha field at every time-step dir and binarises it directly — no
PNG involved. The binarisation is rendering-parameter independent,
so a change in `plot_cartesian`'s DPI, figsize, colormap, or marker
size does not affect the metrics.

## Relationship to `hele-shaw-cells-runnable`

This repo was created as the **blueprint-aligned** version of
[`hele-shaw-cells-runnable`](../hele-shaw-cells-runnable). The two
repos coexist:

| Repo | Purpose | Status |
|---|---|---|
| `hele-shaw-cells-runnable` | Verified Docker-runnable build with a 560-line README and a bit-exact baseline. The original developer artifact. | Unchanged. The source of truth for the working sim. |
| `hele-shaw-cells-example` (this) | Same simulation, restructured to match the [platform instance-repo schema](../NFDI4IngModelValidationPlatform/docs/getting_started/benchmark_addition_guide.md). Has parameters_*.json, a top-level Snakefile, RO-Crate provenance, and a metrics smoke test. | This repo. |
| `NFDI4IngModelValidationPlatform` | The main hub. Lists this example in its benchmark registry. | Unchanged. |
| `hele-shaw-cells/` (upstream) | The 2024 research artifact by Yao Zhang. | Unchanged historical record. |

The Docker image, solver, mesh, fluid properties, and numerics are
**identical** between `hele-shaw-cells-runnable` and this repo. Both
build the same `hele-shaw:latest` image and produce the same
simulation output.

## Publishing

To publish this repo to GitHub and register it with the platform, see
[PUBLISH.md](PUBLISH.md). For the Zenodo DOI workflow, see
[ZENODO.md](ZENODO.md).

## Citing this software

If you use this benchmark in published work, please cite the version of
`hele-shaw-cells-example` that you actually ran. The full machine-readable
citation metadata lives in [`CITATION.cff`](CITATION.cff) and
[`codemeta.json`](codemeta.json) — GitHub renders a "Cite this repository"
button on the sidebar that reads `CITATION.cff`.

Each release is archived on Zenodo:

| Level                | DOI                                                                                            |
|----------------------|------------------------------------------------------------------------------------------------|
| **Concept** (all versions) | [10.5281/zenodo.20728189](https://doi.org/10.5281/zenodo.20728189) — resolves to the latest |
| v1.0.1               | [10.5281/zenodo.20728190](https://doi.org/10.5281/zenodo.20728190)                             |
| v1.0.0               | (release predates the Zenodo webhook; the v1.0.1 deposit supersedes it for citation purposes) |

The **concept DOI** (F1.1) identifies the project across all versions; the
**version DOI** (F1.2) identifies a specific snapshot. Citing a paper that
used this benchmark? Use the version DOI of the exact version you ran.

## License

MIT — see [LICENSE](LICENSE). The OpenFOAM-v2112 base image is
© The OpenFOAM Foundation / ESI Group, licensed under GPL-3.0.

## Acknowledgments

- Original solver and case: Yao Zhang, 2024 (in `hele-shaw-cells/`).
- Solver methodology: based on the isoAdvection library by Johan Roenby.
- OpenFOAM: The OpenFOAM Foundation / ESI Group.
- Base image: opencfd/openfoam-default:2112 (OpenCFD Ltd.).
- Platform schema: NFDI4IngModelValidationPlatform (`Simulation-Benchmarks/`).
