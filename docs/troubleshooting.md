# Troubleshooting

## `docker: command not found`

Install Docker, or use `docker compose` / a remote builder. On macOS,
[Docker Desktop](https://www.docker.com/products/docker-desktop) or
[colima](https://github.com/abiosoft/colima) both work.

## `The requested image's platform (linux/amd64) does not match the detected host platform (linux/arm64/v8)`

Harmless. The `opencfd/openfoam-default:2112` base image is published
as **amd64 only**; Docker automatically uses QEMU emulation when the
host platform doesn't match. The simulation will run correctly but
slower than native (~4× slower than native on Apple Silicon under
colima). There is no arm64-native v2112 image; if you need native
arm64 performance, build OF-v2112 from source.

## `cannot find file "/case/system/controlDict"` (blockMesh)

blockMesh needs a `system/controlDict` even for mesh-only generation.
The `create_mesh.py` script writes a minimal stub for this case. If
you run `blockMesh` manually, copy the stub:

```text
FoamFile { version 2.0; format ascii; class dictionary; object controlDict; }
application blockMesh; startFrom startTime; startTime 0; stopAt endTime;
endTime 0; deltaT 0; writeControl timeStep; writeInterval 1;
```

into `system/controlDict` in your working case directory.

## `Build fails with isoAdvection.H: No such file or directory`

The base image is not the expected one. Make sure the `FROM` line in
`openfoam/Dockerfile` is `opencfd/openfoam-default:2112`, not a CentOS
or Ubuntu image. v2012 and earlier do not ship the `isoAdvection`
source headers.

## `setFields` produces a zero-volume bubble

Confirm that `openfoam/case_template/0/alpha.air.template` renders to
`internalField uniform 0;`. If a non-uniform field is in place, the
cylinder-to-cell filter in `system/setFieldsDict` may not detect any
cell at the centre.

## `Solver crashes early with "Floating point exception"`

The case defaults are tuned for v2112's PIMPLE / isoAdvector numerics.
If you switch OF versions, check `system/fvSchemes` and
`system/fvSolution` for v2012+ keywords (`isoFaceTol`, `snapTol`,
etc.).

## `Container exits with code 1, no log`

The OF environment failed to load. Run interactively to see why:

```bash
docker run --rm -it -v "$PWD/results/1:/case" --entrypoint /bin/bash hele-shaw
# inside the container:
source /usr/lib/openfoam/openfoam2112/etc/bashrc
which heleShawFoam
which blockMesh
```

## `jinja2.exceptions.UndefinedError: 'X' is undefined`

A template references a key that isn't in the parameter JSON. Open
the `.template` file and check the `{{ ... }}` placeholders against
the keys in `parameters_*.json`. The current `parameters_*.json`
files cover all templated values; if you add a new template, also add
the key to all three `parameters_*.json` files.

## Smoke test FAILs on `phase1_volume_fraction` or other metrics

The tolerances in `tests/baseline/metrics_tolerances.json` are
generous enough to absorb solver non-determinism on the same hardware
(see the runnable README's note about isoAdvector non-bit-reproducibility).
If a metric is consistently out of tolerance, that's a real change in
the simulation and you should regenerate the baseline:

```bash
# Re-run the benchmark to produce fresh results
python openfoam/run_benchmark.py --configurations 1

# Copy the fresh metrics into the baseline (only if the change is
# expected!)
cp results/1/solution_metrics.json tests/baseline/metrics_baseline.json
```

## `mesh_<config>.tar.gz` not generated

`create_mesh.py` writes the tarball to the repo root by default. If
the working directory is wrong (e.g. you ran it from inside
`openfoam/`), the tarball will land in the wrong place. Always run it
from the repo root: `python create_mesh.py 1`.

## `OSError: [Errno 24] Too many open files` (many time-step dirs)

If you lower `solver.writeInterval` to a very small value, the
solver writes many time-step directories. The `solution_field_data.zip`
then has hundreds of subdirectories. This is fine; just be aware that
extracting it on a system with a low `ulimit -n` (default 256 on
macOS) may fail. Increase the limit with `ulimit -n 4096` if needed.

## ROHub upload fails with 401 Unauthorized

Check that `ROHUB_USERNAME` and `ROHUB_PASSWORD` environment variables
are set to the *dev* endpoint's credentials, not production. The default
endpoint in `openfoam/upload_to_rohub.py` is the development ROHub at
`https://rohub2020-devel.apps.paas-dev.psnc.pl/`. If you're using
production, change the endpoint URL in the script (and re-run).

Also confirm the credentials are valid by logging in to the ROHub web
portal directly.
