# Hele-Shaw Cells Benchmark

## Problem description

We consider a 2D circular Hele-Shaw cell: two parallel circular plates
separated by a small gap `b`, with an inner disc of radius `R_in` and
an outer disc of radius `R_out`. The cell is filled with a viscous
fluid (here: a "soap" solution), and air is injected at the centre at
a prescribed volumetric flow rate `Q`. The pressure of the injected
air exceeds the hydrostatic pressure in the soap, so the air
displaces the soap in a pattern of viscous fingers. This is the
classic *radial viscous-fingering* problem studied by Saffman, Taylor,
and others.

The flow is modelled in 2D (axisymmetric around the centre, single
cell in the z-direction) using a gap-averaged formulation based on the
power-law viscosity model. The interface between air and soap is
captured by the Volume-of-Fluid method with the `isoAdvector` scheme.

## Geometry

- `R_in = 1.5 mm` (radius of the inlet disc)
- `R_out = 95 mm` (radius of the outer wall)
- `b = 1 mm` (gap width)
- Initial air bubble: cylinder of radius `0.0025 m = 2.5 mm`,
  height `2 × 0.0012 m = 2.4 mm`, centred on the origin

## Mesh

`NPA × NPZ × 1` cells in cylindrical coordinates, with `NPA` cells in
the radial direction and `NPZ` cells in the angular direction. The
`runnable` repo uses the default 60×60 mesh (14400 cells). This
example sweeps:

- `parameters_1.json`: NPA = NPZ = 60 (14400 cells; the reference)
- `parameters_2.json`: NPA = NPZ = 80 (6400 cells — milder refinement)
- `parameters_3.json`: NPA = NPZ = 60, but `Q = 8×10⁻⁷ m³/s` (twice the
  default flow rate)

## Initial condition

The simulation starts from a uniform `alpha.air = 0` field. The
initial air bubble is set up by `setFields` based on
`system/setFieldsDict`: a cylinder of radius `bubble_radius = 2.5 mm`,
height `[bubble_z_min, bubble_z_max] = [-1.2, +1.2] mm`, where
`alpha.air` is set to 1.

## Boundary conditions

- `inlet` (`R = R_in`): `flowRateInletVelocity` with
  `volumetricFlowRate = 4×10⁻⁷ m³/s` (configurations 1 and 2) or
  `8×10⁻⁷ m³/s` (configuration 3).
- `outlet` (`R = R_out`): `inletOutlet`, allowing outflow.
- `plates` (`z = ±b/2`, the top and bottom plates of the cell):
  `fixedValue` velocity (no-slip).

## Fluid properties

`constant/transportProperties` defines two phases:

| Phase | ρ (kg/m³) | k (m²/s) | n (-) |
|---|---|---|---|
| air  | 1.2     | 1.5×10⁻⁵ | 1.0 |
| soap | 1026.6  | 2.0×10⁻³ | 1.0 |

Both phases use the `powerLaw` transport model with `n = 1` (i.e.
Newtonian). The surface tension coefficient is `σ = 0.031 N/m`.

## Solver settings

- `endTime = 15 s`
- `deltaT = 0.1 s` (initial)
- `writeInterval = 0.05 s` (writes every 0.05 s → 301 frames at t=0…15)
- `maxCo = 0.5`, `maxAlphaCo = 0.5` (adaptive timestep)
- `adjustTimeStep = yes`

## Output

The solver writes per-cell fields at every output time:
`alpha.air`, `U`, `p_rgh`, `phi`, plus the previous-time "old" fields
(`alpha.air_0`, `U_0`, `phi_0`) used by `isoAdvector`. ASCII format
is the default; this gives ~720 MB for the full 301-frame run.

The post-processing in `openfoam/run_simulation.py` extracts the five
metrics listed in [the README](../README.md#output-metrics) into
`results/<config>/solution_metrics.json` and packages the time-step
directories, log, and rendered OF dictionaries into
`results/<config>/solution_field_data.zip` with a hand-rolled
`ro-crate-metadata.json` at the root.

## Expected results (configuration 1)

| Quantity | Expected | Notes |
|---|---|---|
| Time-step count | 301 | 0, 0.05, 0.1, …, 15 |
| Final time | 15.0 s | from `15/uniform/time` |
| Phase-1 volume fraction at t=15 | ~0.21 | from the OF log |
| Cumulative continuity error at t=15 | ~5.6×10⁻⁴ | from the OF log |
| Min/Max of alpha.air at t=15 | 0 / 1 | from the OF log |
| Solver log ends with `End` | yes | success signal |

These values are taken from the
[`hele-shaw-cells-runnable`](../hele-shaw-cells-runnable) verification
run and captured as the metrics baseline in
`tests/baseline/metrics_baseline.json`.

## Modifying the parameters

| What you want | Edit this | Re-run needed? |
|---|---|---|
| Run longer (e.g. t=30) | `parameters_1.json: solver.endTime` | yes, with `Allclean` |
| Different flow rate | `parameters_*.json: boundary_conditions.inlet_volumetric_flow_rate` | yes (no clean needed; `0/U` is re-rendered) |
| Bigger initial bubble | `parameters_*.json: initial_condition.bubble_radius` | yes |
| Different fluids | `parameters_*.json: fluids.{air, soap, sigma}` | yes |
| Finer mesh | `parameters_*.json: mesh.{NPA, NPZ}` | yes, with mesh regeneration |
| Larger output | `parameters_*.json: solver.writeInterval` (smaller = more frames) | yes |
| Binary output | `parameters_*.json: solver.writeFormat` (not currently templated; edit `0/U.template` etc.) | yes |

To run with modifications:

```bash
# 1. Edit parameters_*.json
$EDITOR parameters_1.json

# 2. Re-run
python openfoam/run_benchmark.py --configurations 1
```

## Docker image

The image is built on top of `opencfd/openfoam-default:2112` — the
official OpenCFD image with OpenFOAM-v2112 pre-built (full source
tree, headers, `wmake`). We add a 30-second `wmake` of our
`heleShawFoam` solver on top, and install the binary at
`/opt/heleShawFoam`. The `docker-entrypoint.sh` sources the OF
environment and runs `./Allrun` by default.

The image is **amd64 only**; on arm64 hosts, Docker uses QEMU
emulation, which adds ~4× overhead but produces identical results.

## Acknowledgments

- Original solver and case: Yao Zhang, 2024.
- Solver methodology: based on the isoAdvection library by Johan Roenby.
- OpenFOAM: The OpenFOAM Foundation / ESI Group.
- Base image: opencfd/openfoam-default:2112 (OpenCFD Ltd.).
