"""Hand-rolled RO-Crate 1.1 metadata writer.

Writes a small `ro-crate-metadata.json` to the root of the output zip,
describing the simulation run as a RootDataset with PROV-O relations to
its inputs (parameters, tool, OF base image) and outputs (the metrics
JSON, the alpha field snapshots, the log).

This is intentionally minimal: we do not depend on the `metadata4ing`
Snakemake plugin. The structure is what `rocrate` (Python) would
produce for a small dataset; the future ROHub upload step (in a
follow-up) will validate it.

Schema: https://www.researchobject.org/ro-crate/1.1/
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _docker_image_sha(image: str) -> str | None:
    try:
        out = subprocess.run(
            ["docker", "inspect", "--format={{index .Id}}", image],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def write_ro_crate(
    parameters: dict,
    parameters_file: Path,
    case_dir: Path,
    docker_image: str | None,
    run_timestamp: datetime | None = None,
) -> dict[str, Any]:
    """Build the ro-crate-metadata.json content as a dict.

    `case_dir` is the working directory of the run (after the simulation
    has finished); we pull the rendered OF dicts and any post-run files
    from there for the entity list.
    """
    run_timestamp = run_timestamp or datetime.now(timezone.utc)
    parameters_file = Path(parameters_file)
    case_dir = Path(case_dir)

    # Hash the parameters file
    params_sha = _file_sha256(parameters_file)

    # Tool entities
    tool_image_id = _docker_image_sha(docker_image) if docker_image else None
    tool_entities: list[dict] = []
    if tool_image_id:
        tool_entities.append({
            "@id": tool_image_id,
            "@type": "SoftwareApplication",
            "name": f"hele-shaw Docker image ({docker_image})",
            "description": "Custom OpenFOAM-v2112 image with heleShawFoam solver",
        })
    tool_entities.append({
        "@id": "https://github.com/Simulation-Benchmarks/hele-shaw-cells-example",
        "@type": "SoftwareSourceCode",
        "name": "hele-shaw-cells-example",
        "url": "https://github.com/Simulation-Benchmarks/hele-shaw-cells-example",
    })

    # Input entities (parameters, base OF image)
    input_entities: list[dict] = [
        {
            "@id": parameters_file.name,
            "@type": "MediaType",
            "encodingFormat": "application/json",
            "name": "parameter file",
            "sha256": params_sha,
        },
    ]
    if tool_image_id:
        input_entities.append({
            "@id": "opencfd/openfoam-default:2112",
            "@type": "SoftwareApplication",
            "name": "OpenFOAM-v2112 (opencfd base image)",
        })

    # Output entities
    output_entities: list[dict] = []
    for f in sorted(case_dir.glob("**/*")):
        if not f.is_file():
            continue
        if f.name in {"ro-crate-metadata.json", "log.heleShawFoam"}:
            rel = f.name
        elif f.name in {"solution_metrics.json", "solution_field_data.zip"}:
            rel = f.name
        elif f.suffix in {".template", ".py", ".C", ".H"}:
            continue
        else:
            rel = str(f.relative_to(case_dir))
        output_entities.append({
            "@id": rel,
            "@type": "File",
            "name": f.name,
        })
    # Always include the log
    if (case_dir / "log.heleShawFoam").exists():
        output_entities.append({
            "@id": "log.heleShawFoam",
            "@type": "File",
            "name": "log.heleShawFoam",
        })

    # Resolve host platform
    host = {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "docker_version": _docker_version(),
    }

    crate: dict[str, Any] = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "ro-crate-metadata.json",
                "@type": "CreativeWork",
                "about": {"@id": "./"},
                "identifier": "ro-crate-metadata.json",
            },
            {
                "@id": "./",
                "@type": "Dataset",
                "name": "Hele-Shaw Cells Benchmark Run",
                "description": (
                    f"Configuration {parameters.get('configuration', '?')} of the "
                    "hele-shaw-cells-example benchmark. Radial viscous fingering in a "
                    "2D circular Hele-Shaw cell, simulated with OpenFOAM-v2112 + heleShawFoam."
                ),
                "dateCreated": run_timestamp.isoformat(),
                "identifier": params_sha,
                "publisher": {"@id": "https://github.com/Simulation-Benchmarks"},
                "host": host,
                "hasPart": output_entities,
            },
            {
                "@id": "#run",
                "@type": "CreateAction",
                "name": "Simulation run",
                "startTime": run_timestamp.isoformat(),
                "instrument": tool_entities,
                "object": input_entities,
                "result": {"@id": "./"},
            },
        ],
    }
    return crate


def _docker_version() -> str | None:
    try:
        out = subprocess.run(
            ["docker", "--version"],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def write_ro_crate_to_dir(crate: dict, target_dir: Path) -> Path:
    """Write ro-crate-metadata.json into target_dir. Returns the path."""
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    out = target_dir / "ro-crate-metadata.json"
    out.write_text(json.dumps(crate, indent=2, sort_keys=False))
    return out
