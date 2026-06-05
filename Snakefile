"""Top-level Snakefile for the hele-shaw-cells-example benchmark.

Orchestrates:
  - create_mesh.py:           parameters_<config>.json -> mesh_<config>.tar.gz
  - openfoam/run_simulation.py per tool (currently: openfoam)
  - openfoam/summarize_results.py: aggregate metrics into summary.json

Run from the repo root with:
  snakemake --cores 1
"""
import json

configfile: "workflow_config.json"


rule all:
    input:
        "results/summary.json",
        expand(
            "results/{config}/solution_metrics.json",
            config=config["configurations"],
        ),
        expand(
            "results/{config}/solution_field_data.zip",
            config=config["configurations"],
        ),
        expand(
            "results/{config}/fingers.png",
            config=config["configurations"],
        ),


rule create_mesh:
    input: "parameters_{config}.json"
    output: "mesh_{config}.tar.gz"
    shell:
        "python create_mesh.py {wildcards.config}"


rule run_openfoam:
    input:
        params="parameters_{config}.json",
        mesh="mesh_{config}.tar.gz",
    output:
        metrics="results/{config}/solution_metrics.json",
        zip="results/{config}/solution_field_data.zip",
    log: "results/{config}/snakemake.log"
    shell:
        "cd openfoam && "
        "snakemake --cores 1 "
        "--snakefile Snakefile "
        "--config configuration={wildcards.config} "
        "--directory .. "
        "2>&1 | tee ../{log}"


rule summarize:
    input:
        expand(
            "results/{config}/solution_metrics.json",
            config=config["configurations"],
        )
    output: "results/summary.json"
    shell:
        "python openfoam/summarize_results.py {input} --output {output}"


rule plot_fingers:
    input:
        metrics="results/{config}/solution_metrics.json",
    output:
        fig="results/{config}/fingers.png",
    params:
        times="0.05 1 5 10 15",
    shell:
        "python openfoam/plot_fingers.py "
        "--results-dir results/{wildcards.config} "
        "--times {params.times} "
        "--output {output.fig}"
