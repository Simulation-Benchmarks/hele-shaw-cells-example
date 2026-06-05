"""Hand-rolled RO-Crate 1.1 + metadata4ing (m4i) metadata writer.

Writes a small `ro-crate-metadata.json` to the root of the output zip,
describing the simulation run as a RootDataset with PROV-O relations to
its inputs (parameters, tool, OF base image) and outputs (the metrics
JSON, the alpha field snapshots, the log).

The crate also embeds `m4i:`-namespaced predicates from the
metadata4ing ontology (https://w3id.org/nfdi4ing/metadata4ing#), so the
SPARQL queries in the platform's `docs/rohub.md` work out of the box.
The relevant entities/predicates are:

  - `m4i:Method`           — a single computation step (one config's run)
  - `m4i:hasParameter`     — input parameters (NPA, NPZ, flow rate, ...)
  - `m4i:investigates`     — output metrics the method produces
  - `m4i:implementedByTool`— the OpenFOAM / heleShawFoam tool

This is intentionally minimal: we do not depend on the `metadata4ing`
Snakemake plugin. The structure mirrors what the plugin emits for the
plate benchmark, so the platform's cross-benchmark SPARQL queries work
on Hele-Shaw results too.

Schema: https://www.researchobject.org/ro-crate/1.1/
m4i:    https://w3id.org/nfdi4ing/metadata4ing
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# m4i namespace (the platform's metadata4ing ontology)
M4I = "https://w3id.org/nfdi4ing/metadata4ing#"


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


def _flatten(parameters: dict, prefix: str = "") -> list[tuple[str, Any]]:
    """Flatten a nested parameters dict into (dotted_path, leaf_value) pairs.

    Example:
        {"mesh": {"NPA": 60}} -> [("mesh.NPA", 60)]
    """
    out: list[tuple[str, Any]] = []
    for k, v in parameters.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.extend(_flatten(v, key))
        else:
            out.append((key, v))
    return out


def _property_value(label: str, value: Any) -> dict[str, Any]:
    """Build a schema:PropertyValue node for a (label, value) pair.

    The label is the dotted-path key (e.g. "mesh.NPA"); the value is the
    raw Python value (will be stringified into a number/string in the
    JSON-LD output).
    """
    node: dict[str, Any] = {
        "@id": f"#property_{label}",
        "@type": "schema:PropertyValue",
        "rdfs:label": label,
    }
    if isinstance(value, bool):
        node["schema:value"] = "true" if value else "false"
    elif isinstance(value, (int, float)):
        node["schema:value"] = float(value)
    else:
        node["schema:value"] = str(value)
    return node


def _tool_entity() -> dict[str, Any]:
    """The hele-shaw-cells-example tool entity (OpenFOAM + heleShawFoam)."""
    return {
        "@id": "https://github.com/Simulation-Benchmarks/hele-shaw-cells-example#openfoam",
        "@type": "schema:SoftwareApplication",
        "rdfs:label": "openfoam-heleshawfoam",
        "name": "OpenFOAM v2112 + heleShawFoam (custom solver)",
        "url": "https://github.com/Simulation-Benchmarks/hele-shaw-cells-example",
        "description": (
            "2D gap-averaged Hele-Shaw simulation with the power-law viscosity "
            "model and the isoAdvector VOF scheme. Solver source under "
            "openfoam/solver/."
        ),
    }


def write_ro_crate(
    parameters: dict,
    parameters_file: Path,
    case_dir: Path,
    docker_image: str | None,
    run_timestamp: datetime | None = None,
    metrics: dict | None = None,
) -> dict[str, Any]:
    """Build the ro-crate-metadata.json content as a dict.

    Args:
        parameters: the parsed parameters_*.json dict.
        parameters_file: path to the parameters JSON (used for hashing).
        case_dir: working directory of the run (post-simulation).
        docker_image: name of the docker image used (e.g. "hele-shaw:latest").
        run_timestamp: ISO 8601 timestamp; defaults to "now".
        metrics: the parsed solution_metrics dict (the five scalar metrics).
                 If None, no `m4i:investigates` entities are emitted.

    `case_dir` is the working directory of the run (after the simulation
    has finished); we pull the rendered OF dicts and any post-run files
    from there for the entity list.
    """
    run_timestamp = run_timestamp or datetime.now(timezone.utc)
    parameters_file = Path(parameters_file)
    case_dir = Path(case_dir)

    # Hash the parameters file
    params_sha = _file_sha256(parameters_file)

    # ---------- Tool entities ----------
    tool_image_id = _docker_image_sha(docker_image) if docker_image else None
    tool_entities: list[dict] = [_tool_entity()]
    if tool_image_id:
        tool_entities.append({
            "@id": tool_image_id,
            "@type": "schema:SoftwareApplication",
            "name": f"hele-shaw Docker image ({docker_image})",
            "description": "Custom OpenFOAM-v2112 image with heleShawFoam solver",
        })
    tool_entities.append({
        "@id": "https://github.com/Simulation-Benchmarks/hele-shaw-cells-example",
        "@type": "schema:SoftwareSourceCode",
        "name": "hele-shaw-cells-example",
        "url": "https://github.com/Simulation-Benchmarks/hele-shaw-cells-example",
    })

    # ---------- Input entities (parameters file + OF base image) ----------
    input_entities: list[dict] = [
        {
            "@id": parameters_file.name,
            "@type": "schema:MediaObject",
            "encodingFormat": "application/json",
            "name": "parameter file",
            "sha256": params_sha,
        },
    ]
    if tool_image_id:
        input_entities.append({
            "@id": "opencfd/openfoam-default:2112",
            "@type": "schema:SoftwareApplication",
            "name": "OpenFOAM-v2112 (opencfd base image)",
        })

    # ---------- m4i: property values (flattened from parameters) ----------
    flat_params = _flatten(parameters)
    param_property_values = [_property_value(k, v) for k, v in flat_params]

    # ---------- m4i: property values for the metrics (output) ----------
    metrics_property_values: list[dict] = []
    if metrics:
        for k, v in metrics.items():
            if v is None:
                continue
            metrics_property_values.append(
                _property_value(f"metric.{k}", v)
            )

    # ---------- m4i:Method (one per run) ----------
    method_node: dict[str, Any] = {
        "@id": f"#method_configuration_{parameters.get('configuration', '?')}",
        "@type": f"{M4I}Method",
        "rdfs:label": (
            f"heleShawFoam simulation, configuration "
            f"{parameters.get('configuration', '?')}"
        ),
        f"{M4I}hasParameter": [{"@id": pv["@id"]} for pv in param_property_values],
        f"{M4I}implementedByTool": [{"@id": te["@id"]} for te in tool_entities],
    }
    if metrics_property_values:
        method_node[f"{M4I}investigates"] = [
            {"@id": pv["@id"]} for pv in metrics_property_values
        ]

    # ---------- Output entities (files in case_dir) ----------
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
            "@type": "schema:MediaObject",
            "name": f.name,
        })
    if (case_dir / "log.heleShawFoam").exists():
        output_entities.append({
            "@id": "log.heleShawFoam",
            "@type": "schema:MediaObject",
            "name": "log.heleShawFoam",
        })

    # ---------- Host info ----------
    host = {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "docker_version": _docker_version(),
    }

    # ---------- Build the @graph ----------
    graph: list[dict[str, Any]] = [
        {
            "@id": "ro-crate-metadata.json",
            "@type": "CreativeWork",
            "about": {"@id": "./"},
            "identifier": "ro-crate-metadata.json",
        },
        {
            "@id": "./",
            "@type": "Dataset",
            "name": f"Hele-Shaw Cells Benchmark Run (config {parameters.get('configuration', '?')})",
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
        # m4i entities: a single Method per run, plus its parameters
        # (input) and the metrics it produces (output).
        method_node,
    ]
    # Add the parameter / metric PropertyValue nodes to the graph.
    graph.extend(param_property_values)
    graph.extend(metrics_property_values)

    crate: dict[str, Any] = {
        "@context": [
            "https://w3id.org/ro/crate/1.1/context",
            {
                "schema": "https://schema.org/",
                "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
                "m4i": M4I,
            },
        ],
        "@graph": graph,
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
