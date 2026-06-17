# Changelog

All notable changes to this project will be documented in this file.
The format is loosely based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2026-06-17

### Added
- `CITATION.cff` (CFF 1.2.0) for machine-readable citation metadata; includes
  authors Yao Zhang (original solver) and Vasiliy Seibert (maintainer, ORCID
  0000-0002-7121-6816), with placeholder DOIs to be backfilled after the
  first Zenodo deposit is published.
- `codemeta.json` (CodeMeta 2.0) for cross-registrar discoverability.
- `CHANGELOG.md` (this file) for versioned provenance.
- Zenodo DOI badge and "Citing this software" section in `README.md`.
- Tag `v1.0.1` cut to trigger the GitHub-Zenodo webhook and mint the
  first DOI deposit for this repository.

### Notes
- This is a **metadata-only** release. The simulation source code, the
  Docker image, the solver, the mesh, the fluid properties, the numerics,
  and the metrics baseline are unchanged from v1.0.0.
- The Zenodo deposit will use the v1.0.1 tag, not v1.0.0, so the
  `solution_field_data.zip` snapshot includes the new FAIR metadata
  files.

## [1.0.0] - 2026-06-05

### Added
- **Three parameter configurations** (`parameters_1.json`, `parameters_2.json`,
  `parameters_3.json`) forming a minimal convergence + sensitivity study:
  - Config 1: reference (NPA=NPZ=60, Q=4×10⁻⁷ m³/s)
  - Config 2: mild mesh refinement (NPA=NPZ=80)
  - Config 3: flow-rate variation (Q=8×10⁻⁷ m³/s)
- **Mathematical model** in `docs/hele-shaw-cells.md`: full 3D-in-z Navier–
  Stokes + VOF + continuum surface force, the gap-averaged 2D Darcy-type
  reduction, and dimensionless numbers (Ca ≈ 3.6×10⁻³, M = 7.5×10⁻³,
  Re ≈ 29, Pe ≈ 10⁴).
- **Reference finger-pattern image** `docs/hele-shaw-cells.png` extracted
  from the runnable repo's verified run.
- **`openfoam/plot_fingers.py`**: post-run multi-panel alpha-field
  visualizer (polar and Cartesian layouts).
- **`openfoam/ro_crate.py`**: m4i:-namespaced RO-Crate 1.1 writer with
  `m4i:Method` / `m4i:hasParameter` / `m4i:investigates` / `m4i:implementedByTool`
  predicates for cross-benchmark SPARQL compatibility.
- **`notebooks/RoCrate.ipynb`** + **`openfoam/upload_to_rohub.py`**: ROHub
  upload (interactive + headless / CI).
- **Smoke tests** in `tests/compare.py` (alpha-field diff + metrics smoke
  test) with baselines in `tests/baseline/`.
- **CI** (`.github/workflows/run-benchmark.yml`):
  - `run-benchmark` job: runs all 3 configs, smoke-tests against the
    baseline, uploads results as a downloadable artifact
    (`workflow_dispatch` trigger).
  - `rohub-upload` job: uploads results to the dev ROHub on release tags.
  - `notebook-smoke` job: validates and executes the walkthrough notebook
    in fast mode on every push and PR.
- **`notebooks/Simulation_Walkthrough.ipynb`**: end-to-end walkthrough
  (clone → build → math → run → inspect), with a `RUN_SIMULATION=0` fast
  mode for low-resource environments.
- **Documentation** in `docs/`: `hele-shaw-cells.md` (math + problem
  statement), `getting_started.md` (cross-platform install), `troubleshooting.md`,
  `rohub.md` (ROHub + SPARQL).
- **`PUBLISH.md` / `PUBLISHED.md` / `ZENODO.md`**: 7-step publish checklist,
  publish event record, and Zenodo DOI workflow instructions.
- **Docker image** based on `opencfd/openfoam-default:2112`, with a
  30-second `wmake` of `heleShawFoam` installed at `/opt/heleShawFoam`.

### Provenance
- Original solver and case: Yao Zhang, 2024 (in `hele-shaw-cells/`).
- Solver methodology: isoAdvection library by Johan Roenby.
- OpenFOAM: The OpenFOAM Foundation / ESI Group.
- Base image: opencfd/openfoam-default:2112 (OpenCFD Ltd.), GPL-3.0.
- Platform schema: NFDI4IngModelValidationPlatform (`Simulation-Benchmarks/`).
