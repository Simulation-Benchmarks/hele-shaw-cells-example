# Getting started

This guide walks you through installing the prerequisites and running
the Hele-Shaw cells benchmark on your platform. The walkthrough
notebook ([`notebooks/Simulation_Walkthrough.ipynb`](../notebooks/Simulation_Walkthrough.ipynb))
is the recommended path; this page tells you how to set up the host
it runs on.

## 1. Pick your platform

| Platform | Cost | Time to working | Best for |
|---|---|---|---|
| **macOS + Colima** (CPU) | Free | ~5 min | **Recommended for local dev on a Mac.** Lightest Mac-native option. |
| macOS + Docker Desktop | Free for personal use; ~$5/mo Pro | ~5 min | Works but heavier than Colima. |
| macOS + OrbStack | Free for personal use | ~3 min | Fastest Mac-native option, growing user base. |
| **Linux + Docker** (apt) | Free | ~5 min | Best for a Linux box, VM, or WSL2. |
| Windows / WSL2 | Free | ~10 min | WSL2 + Docker Desktop. |
| Paperspace / RunPod (CPU) | $0.20-0.50/hr | ~10 min | Best for a fresh machine without local setup. |
| Hetzner / Oracle Cloud | $0-4/mo | ~5-10 min | Best for an always-on VM. |
| mybinder / Google Colab | Free | ~5-10 min | **For viewing the notebook only; no simulation.** |

The Docker image is the same on every platform (`opencfd/openfoam-default:2112` + our custom `heleShawFoam` solver). What differs is how you install Docker.

## 2. macOS + Colima (recommended for Macs)

This is what we recommend for Apple Silicon and Intel Macs. Colima
runs a Linux VM in the background and exposes the Docker CLI on top of
it. It is much lighter than Docker Desktop (which uses Apple's
hypervisor to run a full Linux VM with a UI).

### Install

```bash
# Install Colima + the Docker CLI.
brew install colima docker

# Start Colima. The defaults (2 CPU, 2 GB RAM, 60 GB disk) are enough
# for the reference 60×60 mesh. For config 2 (80×80) bump to 4 GB.
colima start
# Or, for a heavier config:
#   colima start --cpu 4 --memory 4

# Verify
docker ps
docker run --rm hello-world   # should print "Hello from Docker!"
```

### Clone, set up, and run

```bash
# 1. Clone the repo
git clone https://github.com/Simulation-Benchmarks/hele-shaw-cells-example.git
cd hele-shaw-cells-example

# 2. Set up the workflow Python env (one-time)
mamba env create -n hs-workflow -f environment.yml
conda activate hs-workflow

# 3. (Optional, but speeds up the build) pre-pull the base image
docker pull opencfd/openfoam-default:2112

# 4. Launch the walkthrough notebook
jupyter lab notebooks/Simulation_Walkthrough.ipynb
```

Inside the notebook:

- The first cell detects that you're already in the repo (or walks up to it).
- The third cell builds the image (try `docker buildx build --load`
  first; fall back to legacy `docker build` if your Docker lacks
  the buildx component). ~3 min on a fresh pull.
- The simulation cells (17-21) take ~3-5 min per config on native
  amd64, **~15-20 min per config on Apple Silicon under QEMU**. The
  full sweep (configs 1, 2, 3) takes 30-60 min on Apple Silicon.

If you don't want to wait that long, set `RUN_SIMULATION=0` at the top
of the notebook to skip the simulation and just see the math +
workflow + visualization skeleton. **The fingers figure cell (cell 26)
still runs in fast mode** — if `results/<config>/` is already on disk
from a previous run, the polar and Cartesian figures are rendered
from it without re-running the heavy compute. If `results/` is
missing, the cell prints a clear "no results found" message and skips
that configuration.

### Colima-specific gotchas

- **Daemon not running:** if you see `FileNotFoundError: 'docker'` or
  `dial unix /Users/<you>/.colima/default/docker.sock: no such file or
  directory`, your Colima VM stopped. Run `colima start` and re-run
  the affected cell.
- **Out of memory:** if a config crashes with `OOMKilled`, bump the
  Colima VM: `colima stop && colima start --memory 8`. The 80×80 mesh
  config is the most memory-hungry.
- **Old Docker CLI:** if `docker buildx build --load` says
  `unknown flag: --load`, your Docker version doesn't have the buildx
  component. The notebook's build cell falls back to legacy
  `docker build` automatically; no action needed.
- **Reset Colima:** `colima stop && colima delete && colima start`
  for a clean slate.

## 3. macOS + Docker Desktop

If you already have Docker Desktop installed and prefer it:

```bash
# 1. Make sure Docker Desktop is running (Docker icon in the menu bar).

# 2. Clone, set up, and run
git clone https://github.com/Simulation-Benchmarks/hele-shaw-cells-example.git
cd hele-shaw-cells-example
mamba env create -n hs-workflow -f environment.yml
conda activate hs-workflow
jupyter lab notebooks/Simulation_Walkthrough.ipynb
```

The rest is the same as Colima. **Docker Desktop is heavier than
Colima** (it ships a full UI and a privileged helper), but it has a
slicker interface and integrates with macOS's `docker context`.

## 4. macOS + OrbStack

OrbStack is a recent Mac-native Docker alternative; it's faster than
Colima for many workloads and has a clean UI. Install it from
<https://orbstack.dev/> and then:

```bash
# After installation, the `docker` CLI is automatically wired to OrbStack.
docker ps

# Same recipe as Colima from here on.
git clone https://github.com/Simulation-Benchmarks/hele-shaw-cells-example.git
cd hele-shaw-cells-example
mamba env create -n hs-workflow -f environment.yml
conda activate hs-workflow
jupyter lab notebooks/Simulation_Walkthrough.ipynb
```

## 5. Linux + Docker (Ubuntu / Debian / similar)

```bash
# 1. Install Docker
sudo apt-get update
sudo apt-get install -y docker.io
sudo usermod -aG docker $USER
newgrp docker    # refresh the group
docker ps        # verify (may need a logout/login first)

# 2. Clone and set up
git clone https://github.com/Simulation-Benchmarks/hele-shaw-cells-example.git
cd hele-shaw-cells-example
mamba env create -n hs-workflow -f environment.yml
conda activate hs-workflow
jupyter lab notebooks/Simulation_Walkthrough.ipynb
```

On a native Linux amd64 host, the simulation runs at full speed (~3-5
min per config; ~10-15 min for the full sweep).

## 6. Windows / WSL2

Install WSL2 (Windows Subsystem for Linux) and then a Linux
distribution (Ubuntu is the default). Inside WSL2, follow the **Linux
+ Docker** instructions above.

```powershell
# In PowerShell, install WSL2 with the default Ubuntu distribution.
wsl --install

# Restart, open the Ubuntu terminal, and continue.
```

WSL2 is a real Linux kernel, so the simulation runs at full speed
(no QEMU emulation). Docker Desktop integrates with WSL2 natively.

## 7. Remote VM (Hetzner / Oracle Cloud / Paperspace / RunPod)

If you want to run on a more powerful remote machine, all of these
providers support Docker + Jupyter out of the box. The basic recipe
on each:

```bash
# After SSHing into the VM:
sudo apt-get update && sudo apt-get install -y docker.io mambaforge
sudo usermod -aG docker $USER && newgrp docker
docker ps
mamba env create -n hs-workflow -f environment.yml
conda activate hs-workflow
git clone https://github.com/Simulation-Benchmarks/hele-shaw-cells-example.git
cd hele-shaw-cells-example
jupyter lab --ip 0.0.0.0 --no-browser notebooks/Simulation_Walkthrough.ipynb
# Then point your browser at http://<vm-public-ip>:8888/
```

Provider-specific:

- **Hetzner Cloud** (<https://www.hetzner.com/cloud>): ~€3.79/month for
  a CX22 (2 vCPU, 4 GB RAM, 40 GB SSD). Native amd64, no emulation.
  Cheapest always-on option.
- **Oracle Cloud free tier** (<https://www.oracle.com/cloud/free/>):
  4 OCPUs and 24 GB RAM, free forever (ARM-based Ampere A1). The
  `opencfd/openfoam-default:2112` image is amd64, so ARM-based
  instances will use QEMU emulation (~4× slower than native amd64).
- **Paperspace Gradient** (<https://www.paperspace.com/>): $0.50/hour
  for a CPU container. Comes with Jupyter pre-installed.
- **RunPod** (<https://www.runpod.io/>): $0.20/hour for a CPU
  container. Free GPU quotas exist but are not useful for this
  benchmark (the solver is CPU-bound).

## 8. mybinder / Google Colab (viewing only)

If you just want to see the math + workflow + visualization without
actually running the simulation, the notebook defaults to
`RUN_SIMULATION=0` and works on any host with Python + Jupyter.

- **mybinder** (<https://mybinder.org>): paste the GitHub URL
  `https://github.com/Simulation-Benchmarks/hele-shaw-cells-example`
  and click "launch". The notebook will run in fast mode
  automatically.
- **Google Colab**: in a new Colab notebook, run:
  ```python
  !git clone https://github.com/Simulation-Benchmarks/hele-shaw-cells-example.git
  %cd hele-shaw-cells-example
  !pip install jupyter nbconvert nbformat pandas matplotlib jinja2
  !jupyter nbconvert --to notebook --execute \
      --ExecutePreprocessor.timeout=300 \
      notebooks/Simulation_Walkthrough.ipynb \
      --output Simulation_Walkthrough.executed.ipynb
  ```
  Then open `Simulation_Walkthrough.executed.ipynb` in Colab's
  file browser. (Note: the Colab runtime doesn't have Docker, so
  only fast mode works.)

## 9. Common gotchas (cross-platform)

| Symptom | Cause | Fix |
|---|---|---|
| `FileNotFoundError: 'docker'` | Docker CLI not on PATH, or daemon not running | Install Docker; on macOS, `colima start`. |
| `dial unix ... docker.sock: no such file or directory` | Daemon socket missing | macOS: `colima start`. Linux: `sudo systemctl start docker`. |
| `docker: unknown flag: --load` | Docker lacks the buildx component | The notebook's build cell falls back to legacy `docker build` automatically. No action needed. |
| `Container exited with code 1, no log` | OF environment failed to load inside the container | Run interactively: `docker run -it --entrypoint /bin/bash hele-shaw bash` and `source /usr/lib/openfoam/openfoam2112/etc/bashrc` to debug. |
| `setFields produces a zero-volume bubble` | `0/alpha.air` is non-uniform (a legacy non-uniform field from the original repo) | The templates render `alpha.air` as `uniform 0`. If you've edited the templates, ensure the `uniform 0;` is preserved. |
| Solver runs but `metrics_baseline.json` smoke test fails | Different OF patch level / gcc / parallelism | The tolerances in `tests/baseline/metrics_tolerances.json` are generous; widen them if the failure is small. |

## 10. What's next?

- **Run the walkthrough notebook** on your platform. Set
  `RUN_SIMULATION=1` to actually run the simulation, or
  `RUN_SIMULATION=0` to skip it and just see the math + workflow.
- **Inspect the results** in `results/<config>/`: `solution_metrics.json`,
  `solution_field_data.zip`, `fingers.png`.
- **Run all 3 configurations** by setting `CONFIGURATIONS = "1 2 3"`
  at the top of the notebook.
- **Upload to ROHub** (optional): see [docs/rohub.md](rohub.md) and the
  `notebooks/RoCrate.ipynb` notebook.
- **Modify the simulation**: edit `parameters_1.json` and re-run.
  The workflow auto-discovers new `parameters_*.json` files.

For deeper reference material:

- **Mathematical model**: [docs/hele-shaw-cells.md](hele-shaw-cells.md)
- **Troubleshooting**: [docs/troubleshooting.md](troubleshooting.md)
- **ROHub + SPARQL**: [docs/rohub.md](rohub.md)
- **Walkthrough notebook** (the recommended path): [notebooks/Simulation_Walkthrough.ipynb](../notebooks/Simulation_Walkthrough.ipynb)
