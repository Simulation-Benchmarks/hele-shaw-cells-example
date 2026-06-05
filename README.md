# Hele-Shaw Cells Example

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
- ROHub upload + SPARQL queries: see [docs/rohub.md](docs/rohub.md)
- **Original Docker-runnable build**: [`hele-shaw-cells-runnable`](../hele-shaw-cells-runnable)
- **Original research artifact**: [`hele-shaw-cells/`](../hele-shaw-cells) (Yao Zhang, 2024)

## Quick start

```bash
# 1. Build the OpenFOAM Docker image (one-time, ~3 min on amd64)
cd openfoam
docker build -t hele-shaw:latest .

# 2. Create the workflow Python env (one-time)
mamba env create -n hs-workflow -f ../environment.yml
conda activate hs-workflow

# 3. Generate the workflow config
python generate_config.py

# 4. Run all configurations (3 configs × ~3-5 min on amd64 = 9-15 min)
cd openfoam
python run_benchmark.py

# 5. Inspect results
cat ../results/summary.json
open ../results/phase1_volume_fraction_vs_NPA.pdf
open ../results/phase1_volume_fraction_vs_flow_rate.pdf
```

## What's in this repo

```
hele-shaw-cells-example/
├── README.md                         # this file
├── LICENSE                           # MIT
│
├── docs/
│   ├── hele-shaw-cells.md            # problem statement + parameters
│   └── troubleshooting.md            # common errors and fixes
│
├── parameters_1.json                 # reference config (current defaults)
├── parameters_2.json                 # mesh refinement (NPA=NPZ=80)
├── parameters_3.json                 # flow-rate variation (8×10⁻⁷ m³/s)
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
│   ├── ro_crate.py                   # hand-rolled ro-crate-metadata.json writer
│   ├── _render_templates.py          # case_template/ → working case dir
│   ├── environment_simulation.yml, environment_benchmark.yml, environment_postprocessing.yml
│   ├── meshgen/circulardomain.py     # OF blockMeshDict generator
│   ├── solver/                       # heleShawFoam C++ source
│   ├── case_template/                # OF dicts as Jinja2 templates
│   │   ├── 0/{alpha.air, U, p_rgh}.template
│   │   ├── constant/{g, transportProperties, turbulenceProperties}.template
│   │   ├── system/{controlDict, setFieldsDict}.template
│   │   ├── system/{fvSchemes, fvSolution}      # verbatim
│   │   ├── Allrun, Allclean, case2D.foam
│   │   └── Results/                  # the original reference AVI
│   └── tests_docker/run_container.sh
│
├── benchmark/
│   ├── hele-shaw-cells-example.zip   # the benchmark bundle (auto-generated)
│   └── build_benchmark_zip.py        # reproducible build script
│
├── results/                          # produced at runtime; .gitignored
│
├── tests/
│   ├── compare.py                    # alpha-field diff AND metrics smoke test
│   ├── baseline/                     # captured from a verified run
│   │   ├── alpha.air_t0.05, alpha.air_t15, log.heleShawFoam
│   │   ├── metrics_baseline.json     # the 5 reference values
│   │   └── metrics_tolerances.json
│   └── baseline_v2112_arm64/         # cross-platform comparison
│
├── environment.yml, environment_benchmarks.yml
│
└── .github/workflows/run-benchmark.yml
```

## Relationship to `hele-shaw-cells-runnable`

This repo was created as the **blueprint-aligned** version of
[`hele-shaw-cells-runnable`](../hele-shaw-cells-runnable). The two
repos coexist:

| Repo | Purpose | Status |
|---|---|---|
| `hele-shaw-cells-runnable` | Verified Docker-runnable build with a 560-line README and a bit-exact baseline. The original developer artifact. | Unchanged. The source of truth for the working sim. |
| `hele-shaw-cells-example` (this) | Same simulation, restructured to match the [platform instance-repo schema](../NFDI4IngModelValidationPlatform/docs/getting_started/benchmark_addition_guide.md). Has parameters_*.json, a top-level Snakefile, RO-Crate provenance, and a metrics smoke test. | This repo. |
| `NFDI4IngModelValidationPlatform` | The main hub. Eventually lists this example in its benchmark registry. | Unchanged. |
| `hele-shaw-cells/` (upstream) | The 2024 research artifact by Yao Zhang. | Unchanged historical record. |

The Docker image, solver, mesh, fluid properties, and numerics are
**identical** between `hele-shaw-cells-runnable` and this repo. Both
build the same `hele-shaw:latest` image and produce the same
simulation output.

## Output metrics

Each configuration produces `results/<config>/solution_metrics.json`
with these five metrics:

| Metric | Description | Typical value (config 1) |
|---|---|---|
| `phase1_volume_fraction` | Air volume fraction at endTime, as reported by the solver | ~0.21 |
| `cumulative_continuity_error` | Final cumulative mass-balance error | ~5.6×10⁻⁴ |
| `interface_length_proxy` | Cells with 0 < α < 1 (proxy for the air-cluster perimeter) | ~2141 |
| `wall_time_seconds` | OF `ExecutionTime` | depends on host |
| `time_step_count` | Number of write-time directories produced | 301 |

## Publishing

To publish this repo to GitHub and register it with the platform, see
[PUBLISH.md](PUBLISH.md).

## License

MIT — see [LICENSE](LICENSE). The OpenFOAM-v2112 base image is
© The OpenFOAM Foundation / ESI Group, licensed under GPL-3.0.

## Acknowledgments

- Original solver and case: Yao Zhang, 2024 (in `hele-shaw-cells/`).
- Solver methodology: based on the isoAdvection library by Johan Roenby.
- OpenFOAM: The OpenFOAM Foundation / ESI Group.
- Base image: opencfd/openfoam-default:2112 (OpenCFD Ltd.).
- Platform schema: NFDI4IngModelValidationPlatform (`Simulation-Benchmarks/`).
