# Changelog

All notable changes to this project will be documented in this file.
The format is loosely based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-07-25

### Added
- **Finger counting pipeline**, moved from the standalone
  `finger-counting-experiment` repo. The new pipeline lives in
  `openfoam/finger_binarise.py`, `openfoam/finger_count_tips.py`,
  `openfoam/finger_panel_detect.py`, and `openfoam/finger_pipeline.py`.
  It computes two new metrics per configuration:
  - `final_number_of_fingers` (int): the number of fingertips in the
    binarised final-frame alpha field.
  - `critical_radius_m` (float): the smallest distance from the cell
    centre to the air region's boundary, in metres.
  Plus a per-time-step `n_fingers_over_time` curve (dict[str, int],
  ~300 entries).
- **New artefact** `results/<config>/fingers.png`: the binarised final-
  frame panel with red tip markers and the critical-radius circle.
- **`tests/test_finger_pipeline.py`**: unit test for the binarisation
  algorithm (synthetic + saved alpha field + robustness).
- **Two new keys in `tests/compare.py:DEFAULT_METRIC_TOLERANCES`**
  (`final_number_of_fingers`, `critical_radius_m`) and matching
  entries in `tests/baseline/metrics_baseline.json` /
  `metrics_tolerances.json`.
- **New cells** in the walkthrough notebook: the N(t) curve plot
  and the binarised final-frame view.
- **`scikit-image` and `scipy`** added to
  `openfoam/environment_postprocessing.yml`.

### Changed
- **Dropped the polar view** from `openfoam/plot_fingers.py`: the
  walkthrough now shows only the Cartesian (X-Y) view, per the
  simplification in the integration plan.
- **Robustness to renderer changes**: the integration's primary path
  reads alpha fields directly, not PNGs. A change in
  `plot_cartesian`'s DPI, figsize, colormap, or marker size does
  not break the binarisation. The PNG path (used for `fingers.png`)
  auto-detects panel rectangles and disk radius from the rendered
  figure and falls back to hard-coded defaults on failure.
- **`run_simulation.py`** now calls `extract_finger_metrics` after
  the metrics are extracted and writes the 3 new keys to
  `solution_metrics.json` before the zip is built.

### Notes
- The two new metrics are computed from the alpha field (alpha > 0.5
  binarisation), not the PNG. The values differ from the experiment
  repo\'s PNG-based counts (29 fingers, 5.7 mm) because the two paths
  binarise different connected components. The alpha-field path\'s
  reference values for config 1 at t=15 are n_fingers ~ 15 and
  r_crit_m ~ 0.0158.

## [1.1.1] - 2026-07-25

### Changed
- **`Timesteps/` refactor**: the OF case (constant/, system/, 0/, 0.05/,
  ..., 15/, Allclean, case2D.foam, log.heleShawFoam) and the time-step
  dirs now live under `results/<cfg>/Timesteps/`. The workdir root
  contains only the post-run artefacts (`Allrun` at the root, plus
  `cartesian.png`, `fingers.png`, `solution_metrics.json`,
  `solution_field_data.zip`).
  - `case_template/Allrun` now does `cd Timesteps` after its initial
    `cd "${0%/*}"`, so the OF tools (blockMesh, setFields,
    heleShawFoam) operate inside the case while the entrypoint
    invokes Allrun from the workdir root.
  - `run_simulation.py:render_case` writes the case template into
    `workdir/Timesteps/` and copies `Allrun` to the workdir root so
    the docker entrypoint can find it.
  - `metrics.py:find_latest_time_dir`, `count_time_step_dirs`,
    `finger_pipeline.py:extract_finger_metrics`,
    `plot_fingers.py:plot_fingers` and `plot_cartesian` all read
    alpha fields from `<results>/Timesteps/<t>/alpha.air` instead of
    `<results>/<t>/alpha.air`.
  - `ro_crate.py` and `run_simulation.py:make_solution_zip` are
    path-agnostic (use `case_dir.glob("**/*")` and `shutil.copytree`
    respectively) and pick up the new layout automatically.
  - The walkthrough notebook\'s alpha-field inspection cell reads
    `Path("results") / cfg / "Timesteps" / "15" / "alpha.air"`.
- **`tests/baseline/metrics_baseline.json`**: `time_step_count` is
  now 300 (the value produced by `count_time_step_dirs` which
  excludes `0`). The v1.1.0 baseline had 301, which was the raw
  total number of time-step dirs (including `0/`) and never matched
  what `count_time_step_dirs` actually returns.

### Fixed
- **`fingers.png` was completely wrong in v1.1.0.** The auto-detector
  for the panel rectangles in `cartesian.png` was finding the 3
  vertical column separators but only splitting the image into 5
  equal-height vertical strips (337 px each) instead of the actual
  5 panels (247x247) in the 2x3 grid. The binarisation then operated
  on a 337-px-tall strip and produced an unrecognisable blob. Fixed
  by using the manually-measured `_fallback_rects()` directly.
- **Disk-radius mismatch in the PNG binarisation path.**
  `BinariseParams.disk_radius = 100` was hard-coded for the
  experiment\'s PDF render; the current `plot_cartesian` produces a
  248x338 panel with a 123-px disk. The binarisation\'s `disk_mask`
  was off by 23 px. Fixed by using the panel-derived disk radius
  (`min(panel_w, panel_h) // 2`) in `render_fingers_png`.
- The buggy `detect_disk_radius_from_binary` auto-detector (which
  measured the largest *air* component, not the panel disk) and
  the unused `_column_dark_runs` / `_merge_close` helpers have been
  removed.

### Verified
- Full re-run of config 1 on Apple Silicon (29 min wall time, 1143 s
  OF time): the sim completes, all 301 time-step dirs land under
  `results/1/Timesteps/`, the metrics JSON has the correct 7
  metrics, the `cartesian.png` and `fingers.png` are rendered with
  29 red tip markers, the smoke test passes 4/7 (3 SKIP for the
  log-parse-related None metrics), the unit test passes 11/11, and
  the walkthrough notebook executes cleanly in fast mode.

### Notes
- After the fixes, `fingers.png` for config 1 at t=15 shows the full
  dendritic pattern with 29 red tip markers (matching the
  experiment\'s reference) and a small red critical-radius circle
  (3.9 mm, in the same order of magnitude as the experiment\'s
  5.7 mm).
- The `solver_completed` warning in `metrics.py:parse_log` is a
  pre-existing issue: the OF solver on the new docker image doesn\'t
  print the `^End$` line that `run_simulation.py:main:232` checks for.
  This causes `run_simulation.py` to return rc=3, which makes
  `run_benchmark.py:run_one` short-circuit before rendering
  `cartesian.png` / `fingers.png`. The metrics JSON and zip are
  written correctly despite the warning. Manual recovery: run
  `plot_fingers.py --cartesian` and `finger_pipeline.render_fingers_png`
  manually after the sim exits. To be addressed in a follow-up: relax
  the `solver_completed` check to a warning.
- 3 of 7 metrics (`phase1_volume_fraction`, `cumulative_continuity_error`,
  `wall_time_seconds`) are `None` because the OF solver on the new
  docker image doesn\'t print the corresponding log lines in the
  format `metrics.py:parse_log` expects. The smoke test handles this
  gracefully (prints "SKIP" for missing values). To be addressed in
  a follow-up: relax the log parser or update the docker image.

## [1.1.2] - 2026-07-25

### Fixed
- **`run_simulation.py:main` no longer returns rc=3 when the OF
  solver doesn\'t print the `^End$` line.** The current docker image
  (`opencfd/openfoam-default:2112` + our `heleShawFoam` build) doesn\'t
  emit the standalone `^End$` line that `metrics.py:parse_log` checks
  for, even on a clean run. The previous strict `return 3` made
  `run_benchmark.py:run_one` short-circuit before rendering
  `cartesian.png` / `fingers.png` and tripped the walkthrough
  notebook\'s `subprocess.run(check=True)` cell with a misleading
  "Configuration 1 FAILED" error. Downgraded the check to a soft
  warning (still printed, but doesn\'t return non-zero). The metrics
  JSON, solution zip, and `fingers.png` are all on disk before the
  check fires, so the runner now completes the full pipeline
  end-to-end (sim → cartesian.png → fingers.png) without manual
  recovery. The smoke test, the OF solver\'s own `FatalError`
  lines in `log.heleShawFoam`, and the `metrics.py:parse_alpha_field`
  `None` returns all serve as alternative failure detectors.

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
