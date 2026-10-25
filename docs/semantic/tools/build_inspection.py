#!/usr/bin/env python3
"""Build/execute the cheap inspection notebook; never execute the simulation notebook.

Runtime notebook dependencies: numpy, pandas, matplotlib and IPython. Build also
uses nbformat, nbclient, nbconvert and BeautifulSoup. All scientific inputs are
read from the pinned Git revision; execution uses an isolated temporary snapshot.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

import nbformat as nb
from nbclient import NotebookClient
from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpecManager

ROOT = Path(__file__).resolve().parents[3]
HERE = ROOT / "docs/semantic"
REVISION = "8ec1b34f0a8fdbc103f35f88cba20e12b465800b"
SOURCES = ["parameters_1.json", "parameters_2.json", "parameters_3.json",
           "tests/baseline/metrics_baseline.json", "tests/baseline/metrics_tolerances.json",
           "tests/compare.py", "notebooks/Simulation_Walkthrough.ipynb"]
HEADINGS = ["1. Locate and verify sources", "2. Inspect the parameter sweep",
            "3. Read saved results and missing values", "4. Check reference regression",
            "5. Compare recorded outcomes and figures"]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def make_notebook(hashes):
    cells = []

    def markdown(text):
        cells.append(nb.v4.new_markdown_cell(text.strip(), id=f"inspection-{len(cells):02}"))

    def code(text):
        cells.append(nb.v4.new_code_cell(text.strip(), id=f"inspection-{len(cells):02}"))

    markdown("""# Inspect Hele-Shaw results with Python

Run these five cells in order with **numpy, pandas and matplotlib** installed.
They inspect committed parameters, reference tolerances and the saved simulation
walkthrough. **No Docker, OpenFOAM, simulation, upload or network request is run.**
The original simulation notebook is read as JSON, never executed.

Tables and the comparison plot are recomputed from saved, rounded numbers.
The finger curves and final masks are original saved images, not newly computed
trajectories. Missing measurements remain missing. These are simulation
regression/sensitivity comparisons, not experimental validation.

The repository must already be cloned. Start inside it, in a parent directory
containing `hele-shaw-cells-example`, or set `HELE_SHAW_REPO` to its location.
The notebook works without internet after cloning.

## Contents
""" + "\n".join(f"{i}. [{heading.split('. ', 1)[1]}](#{heading.replace(' ', '-')})"
                 for i, heading in enumerate(HEADINGS, 1)) + """

[Companion Python source](inspect_results.py) ·
[Saved original walkthrough](Simulation_Walkthrough.html)
""")
    markdown("## " + HEADINGS[0])
    code('''from pathlib import Path
import os
import hashlib
import json
import base64
import io
import re
from html.parser import HTMLParser
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, Image, Markdown

def sha256(data):
    return hashlib.sha256(data).hexdigest()

def locate_repository():
    override = os.environ.get("HELE_SHAW_REPO")
    candidates = [Path(override).expanduser()] if override else []
    for parent in (Path.cwd(), *Path.cwd().parents):
        candidates.extend([parent, parent / "hele-shaw-cells-example",
                           parent / "work" / "hele-shaw-cells-example"])
    candidates.append(Path.home() / "work" / "hele-shaw-cells-example")
    for candidate in candidates:
        if (candidate / "parameters_1.json").is_file() and (candidate / "notebooks/Simulation_Walkthrough.ipynb").is_file():
            return candidate.resolve()
    raise FileNotFoundError("Clone hele-shaw-cells-example first, then run from inside it or set HELE_SHAW_REPO to its absolute path. This inspection does not download files.")

ROOT = locate_repository()
''' + f'REVISION = {REVISION!r}\nEXPECTED_HASHES = {hashes!r}\n' + '''
for name, expected in EXPECTED_HASHES.items():
    if sha256((ROOT / name).read_bytes()) != expected:
        raise ValueError(f"{name} differs from reviewed revision {REVISION}. Restore the reviewed scientific inputs before comparing results.")
OUT = ROOT / "docs/semantic/data/inspection"
OUT.mkdir(parents=True, exist_ok=True)
print(f"Verified {len(EXPECTED_HASHES)} committed scientific sources at {REVISION}.")
print("Only lightweight inspection runs below; the original notebook is never executed.")
''')
    markdown("## " + HEADINGS[1] + """

Configuration 2 refines both in-plane mesh indices; configuration 3 doubles
inlet volumetric flow. Other supplied fields are checked for equality, so the
table describes the actual JSON files rather than stale notebook commentary.
""")
    code('''parameters = {str(i): json.loads((ROOT / f"parameters_{i}.json").read_text()) for i in (1, 2, 3)}
parameter_table = pd.DataFrame([
    {"configuration": cfg, "NPA": p["mesh"]["NPA"], "NPZ": p["mesh"]["NPZ"],
     "NPB": p["mesh"]["NPB"], "flow_m3_s": p["boundary_conditions"]["inlet_volumetric_flow_rate"],
     "outer_radius_m": p["domain"]["R_out"], "gap_m": p["domain"]["b"],
     "end_time_s": p["solver"]["endTime"], "write_interval_s": p["solver"]["writeInterval"]}
    for cfg, p in parameters.items()
]).set_index("configuration")
def flatten(values, prefix=""):
    return {key: value for name, value in values.items()
            for key, value in (flatten(value, prefix + name + ".").items()
                               if isinstance(value, dict) else [(prefix + name, value)])}
reference_parameters = flatten(parameters["1"])
changes = [{"configuration": cfg, "parameter": key, "reference": reference_parameters[key], "value": value}
           for cfg in ("2", "3") for key, value in flatten(parameters[cfg]).items()
           if key != "configuration" and value != reference_parameters[key]]
assert {r["parameter"] for r in changes if r["configuration"] == "2"} == {"mesh.NPA", "mesh.NPZ"}
assert {r["parameter"] for r in changes if r["configuration"] == "3"} == {"boundary_conditions.inlet_volumetric_flow_rate"}
display(parameter_table)
display(pd.DataFrame(changes))
parameter_table.to_csv(OUT / "parameters.csv")
''')
    markdown("## " + HEADINGS[2] + """

Read the saved HTML table in source cell 24 (zero-based index 23). It contains
three configurations and seven metrics. Radius values are displayed to six
decimal places; this inspection does not reconstruct hidden precision.
`None` becomes a missing numeric value (`NaN`), with no imputation or baseline
substitution. The original regression transcript is preserved separately.
""")
    code('''walkthrough = json.loads((ROOT / "notebooks/Simulation_Walkthrough.ipynb").read_text())
class TableRows(HTMLParser):
    def __init__(self):
        super().__init__(); self.rows = []; self.row = []; self.value = None
    def handle_starttag(self, tag, attrs):
        if tag == "tr": self.row = []
        if tag in ("th", "td"): self.value = ""
    def handle_data(self, data):
        if self.value is not None: self.value += data
    def handle_endtag(self, tag):
        if tag in ("th", "td"):
            self.row.append(self.value.strip()); self.value = None
        if tag == "tr": self.rows.append(self.row)

saved_table_html = "".join(walkthrough["cells"][23]["outputs"][0]["data"]["text/html"])
parser = TableRows(); parser.feed(saved_table_html)
metric_names = parser.rows[0][1:]
source_rows = [row for row in parser.rows if row[0] in ("1", "2", "3")]
assert len(source_rows) == 3 and len(metric_names) == 7
saved_metrics = pd.DataFrame(
    [[np.nan if value in ("None", "NaN", "nan") else float(value) for value in row[1:]] for row in source_rows],
    index=pd.Index([row[0] for row in source_rows], name="configuration"), columns=metric_names)
missing_metrics = ["phase1_volume_fraction", "cumulative_continuity_error", "wall_time_seconds"]
assert saved_metrics[missing_metrics].isna().all().all()
assert saved_metrics.isna().sum().sum() == 9
display(saved_metrics)
display(saved_metrics.isna().rename_axis("configuration").rename(columns=lambda name: name + " missing"))
saved_metrics.to_csv(OUT / "recorded-metrics.csv", na_rep="")
saved_transcript = "".join(walkthrough["cells"][24]["outputs"][0]["text"])
(OUT / "original-regression-transcript.txt").write_text(saved_transcript)
print("Preserved 9 missing entries across 3 configurations. No missing metric was filled.")
''')
    markdown("## " + HEADINGS[3] + """

Recompute descriptive tolerance decisions from the **rounded saved table**
against the committed configuration-1 baseline. All tolerances are absolute,
except wall time (relative); step count is exact. Missing inputs yield `SKIP`.
The original transcript passed the changed configuration as the `baseline`
argument; the current table labels reference and recorded values explicitly.
Its available absolute-tolerance decisions are unchanged.

Configuration 1 is the reference regression. Configurations 2 and 3 deliberately
change inputs; their out-of-tolerance values are sensitivity outcomes, not proof
of a defective solver. Passing this inspection is not a new simulation or an
experiment-versus-simulation validation.
""")
    code('''baseline = json.loads((ROOT / "tests/baseline/metrics_baseline.json").read_text())
tolerances = json.loads((ROOT / "tests/baseline/metrics_tolerances.json").read_text())
comparisons = []
for cfg, values in saved_metrics.iterrows():
    for metric, recorded in values.items():
        reference = baseline[metric]
        tolerance = tolerances[metric]
        mode = "relative" if metric == "wall_time_seconds" else "absolute"
        delta = np.nan if pd.isna(recorded) else abs(recorded - reference)
        limit = tolerance * abs(reference) if mode == "relative" else tolerance
        status = "SKIP" if pd.isna(recorded) else ("PASS" if delta <= limit else "FAIL")
        comparisons.append(dict(configuration=cfg, metric=metric, reference=reference,
                                recorded=recorded, delta=delta, tolerance=tolerance,
                                tolerance_mode=mode, status=status))
comparison_table = pd.DataFrame(comparisons)
outcomes = pd.crosstab(comparison_table.configuration, comparison_table.status).reindex(columns=["PASS", "FAIL", "SKIP"], fill_value=0)
assert outcomes.loc["1"].tolist() == [4, 0, 3]
assert outcomes.loc["2"].tolist() == [2, 2, 3]
assert outcomes.loc["3"].tolist() == [3, 1, 3]
recorded_decisions = {}
current = None
for line in saved_transcript.splitlines():
    match = re.search(r"Smoke test: configuration (\\d+)", line)
    if match: current = match.group(1)
    match = re.match(r"compare.py: (\\w+): (PASS|FAIL|SKIP)", line)
    if match: recorded_decisions[(current, match.group(1))] = match.group(2)
assert all(recorded_decisions[(r.configuration, r.metric)] == r.status for r in comparison_table.itertuples())
display(comparison_table)
display(outcomes)
comparison_table.to_csv(OUT / "recomputed-comparisons.csv", index=False, na_rep="")
outcomes.to_csv(OUT / "comparison-summary.csv")
print("All 21 recomputed status decisions match the saved transcript (including 9 skipped checks).")
''')
    markdown("## " + HEADINGS[4] + """

The first figure is **newly plotted from recorded scalar values**. A mesh-dependent
interface proxy is not a physical interface length, and this three-case comparison
does not establish mesh convergence. Radii retain the saved table's precision.

The following six figures are **exact saved PNGs** from source cell 31
(zero-based index 30): for each configuration, finger count over time, then the
final binary mask. Their raw numeric time series are not committed here. They
are redisplayed without tracing, interpolation or a new finger extraction run.
""")
    code('''figure, axes = plt.subplots(1, 3, figsize=(12, 3.5), layout="constrained")
colors = ["#427da3", "#aa8243", "#7b669f"]
plot_specs = [("interface_length_proxy", "Recorded interface proxy", "proxy (cell based)", 1),
              ("final_number_of_fingers", "Recorded final finger count", "fingers", 1),
              ("critical_radius_m", "Recorded critical radius", "mm", 1000)]
for ax, (metric, title, unit, scale) in zip(axes, plot_specs):
    ax.bar(saved_metrics.index, saved_metrics[metric] * scale, color=colors)
    ax.set(title=title, xlabel="Configuration", ylabel=unit)
    ax.grid(axis="y", alpha=.2); ax.set_axisbelow(True)
figure.suptitle("New inspection plot from rounded saved metrics; no new simulation")
figure.savefig(OUT / "recorded-outcomes.png", dpi=140)
display(Image(filename=str(OUT / "recorded-outcomes.png")))
plt.close(figure)
image_provenance = []
for cfg, output_indices in (("1", (1, 2)), ("2", (4, 5)), ("3", (7, 8))):
    display(Markdown(f"### Configuration {cfg}: saved curve and final mask"))
    for kind, output_index in zip(("finger-count-curve", "final-mask"), output_indices):
        image_data = base64.b64decode(walkthrough["cells"][30]["outputs"][output_index]["data"]["image/png"])
        image_name = f"saved-config-{cfg}-{kind}.png"
        (OUT / image_name).write_bytes(image_data)
        image_provenance.append(dict(configuration=cfg, kind=kind, sourceCellIndex=30,
                                     sourceOutputIndex=output_index, file=image_name, sha256=sha256(image_data)))
        display(Image(data=image_data))
report = {"revision": REVISION, "sources": EXPECTED_HASHES,
          "simulationExecuted": False, "originalNotebookExecuted": False,
          "uploadExecuted": False, "numericTrajectoriesAvailable": False,
          "metricPrecision": "Exactly the saved HTML table; radius rounded to 6 decimals",
          "missingMetricEntries": int(saved_metrics.isna().sum().sum()),
          "statusDecisionsMatchSavedTranscript": True,
          "newPlot": "recorded-outcomes.png", "savedImages": image_provenance}
(OUT / "provenance.json").write_text(json.dumps(report, indent=2) + "\\n")
print("Saved inspection tables, the new scalar comparison plot, and exact original figures with provenance.")
''')
    return nb.v4.new_notebook(cells=cells, metadata={
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
        "hele_shaw_inspection": {"revision": REVISION, "simulationExecuted": False}})


def render_preview(notebook, sections):
    from bs4 import BeautifulSoup
    from nbconvert import HTMLExporter
    exporter = HTMLExporter(template_name="classic", exclude_input_prompt=True, exclude_output_prompt=True)
    body, _ = exporter.from_notebook_node(notebook)
    soup = BeautifulSoup(body, "html.parser")
    for tag in soup.find_all(["script", "style", "link", "head"]):
        tag.decompose()
    content = soup.find(id="notebook-container")
    for section in sections:
        heading = next(h for h in content.find_all("h2") if h.get_text().rstrip("¶") == section["heading"])
        heading["id"] = section["previewAnchor"]
    for image in content.find_all("img"):
        image["alt"] = "Hele-Shaw inspection figure; source and saved/new status are described in the preceding text."
    for link in content.find_all("a", href=True):
        if link["href"].startswith("#"):
            for section in sections:
                if link["href"] == "#" + section["anchor"]:
                    link["href"] = "#" + section["previewAnchor"]
    return f'''<!doctype html><html lang="en" class="document-view"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Inspect results with Python — Hele-Shaw</title>
<link rel="stylesheet" href="../tokens.css"><link rel="stylesheet" href="../style.css"><link rel="stylesheet" href="notebook.css"></head>
<body data-view="notebook"><header><a class="brand" href="../index.html#overview">Simulation-Benchmarks/<wbr>hele-shaw-cells-example</a><nav aria-label="Main navigation"><a href="../index.html#overview">Semantic Model</a><a href="../index.html#workflows" aria-current="page">Workflows</a><a href="../index.html#nfdi4ing">NFDI4Ing Use Cases</a></nav></header>
<main id="notebook-page"><nav class="notebook-actions"><a href="../index.html#workflow-inspect-results">← Back to workflow</a><a href="inspect_results.ipynb" download>Download runnable notebook</a><a href="inspect_results.py">Python source</a></nav>
<p class="notebook-status">Executed lightweight inspection · 5 stages · No new simulation</p>{content}</main></body></html>\n'''


def execute_notebook(notebook, raw):
    with tempfile.TemporaryDirectory(prefix="hele-shaw-inspection-") as temp:
        temp = Path(temp)
        snapshot = temp / "hele-shaw-cells-example"
        for path, content in raw.items():
            target = snapshot / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        kernel = temp / "kernels/python3"
        kernel.mkdir(parents=True)
        (kernel / "kernel.json").write_text(json.dumps({
            "argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
            "display_name": "Python 3", "language": "python",
            "env": {"MPLCONFIGDIR": str(temp / "mpl"), "IPYTHONDIR": str(temp / "ipython"),
                    "XDG_CACHE_HOME": str(temp / "cache"), "PYDEVD_DISABLE_FILE_VALIDATION": "1",
                    "MPLBACKEND": "Agg"}}))
        manager = KernelManager(kernel_name="python3", kernel_spec_manager=KernelSpecManager(
            kernel_dirs=[str(temp / "kernels")], ensure_native_kernel=False))
        try:
            NotebookClient(notebook, km=manager, timeout=120,
                           resources={"metadata": {"path": str(temp)}}).execute()
        finally:
            if manager.has_kernel:
                manager.shutdown_kernel(now=True)
        destination = HERE / "data/inspection"
        destination.mkdir(parents=True, exist_ok=True)
        for output in (snapshot / "docs/semantic/data/inspection").iterdir():
            shutil.copyfile(output, destination / output.name)
    for cell in notebook.cells:
        cell.metadata.pop("execution", None)
    nb.validate(notebook)
    return notebook


def validate_saved(notebook, hashes):
    expected = make_notebook(hashes)
    assert len(notebook.cells) == len(expected.cells), "Inspection cell count changed"
    for actual, reference in zip(notebook.cells, expected.cells):
        assert (actual.cell_type, actual.source, actual.id) == (reference.cell_type, reference.source, reference.id), "Inspection inputs differ from the builder; use --execute after reviewing the change"
    code_cells = [cell for cell in notebook.cells if cell.cell_type == "code"]
    assert [cell.execution_count for cell in code_cells] == [1, 2, 3, 4, 5], "Inspection needs five saved successful executions"
    assert not any(output.output_type == "error" for cell in code_cells for output in cell.outputs), "Inspection contains an execution error"
    manifest = json.loads((HERE / "data/python-inspection-manifest.json").read_text())
    assert manifest["sources"] == hashes and manifest["revision"] == REVISION
    for path, expected_hash in manifest["outputs"].items():
        assert digest((HERE / path).read_bytes()) == expected_hash, f"Inspection output changed: {path}"
    for path, expected_hash in hashes.items():
        assert digest((ROOT / path).read_bytes()) == expected_hash, f"Scientific source changed: {path}"


def build(execute=False):
    raw = {p: subprocess.check_output(["git", "show", f"{REVISION}:{p}"], cwd=ROOT) for p in SOURCES}
    hashes = {p: digest(content) for p, content in raw.items()}
    destination = HERE / "notebooks/inspect_results.ipynb"
    if execute:
        notebook = execute_notebook(make_notebook(hashes), raw)
        nb.write(notebook, destination)
    else:
        if not destination.is_file():
            raise FileNotFoundError("Saved inspection notebook absent. Explicitly run build_inspection.py --execute to generate it.")
        notebook = nb.read(destination, as_version=4)
        validate_saved(notebook, hashes)
    source_lines = destination.read_text().splitlines()
    python_lines = ["# Generated by tools/build_inspection.py; same five cells as inspect_results.ipynb.", ""]
    sections = []
    number = 0
    for index, cell in enumerate(notebook.cells):
        if cell.cell_type == "markdown":
            python_lines += ["# %% [markdown]", *["# " + line if line else "#" for line in cell.source.splitlines()], ""]
            continue
        number += 1
        heading_cell = notebook.cells[index - 1]
        heading = HEADINGS[number - 1]
        start = len(python_lines) + 1
        python_lines += [f"# %% Cell {number}: {heading.split('. ', 1)[1]}", *cell.source.splitlines()]
        sections.append(dict(number=number, heading=heading, anchor=heading.replace(" ", "-"),
                             previewAnchor=f"inspection-stage-{number}", cellId=cell.id,
                             markdownCellId=heading_cell.id, cellIndex=index,
                             sourceLine=next(i for i, line in enumerate(source_lines, 1) if f'"id": "{heading_cell.id}"' in line),
                             pythonStartLine=start, pythonEndLine=len(python_lines)))
        python_lines.append("")
    (HERE / "notebooks/inspect_results.py").write_text("\n".join(python_lines).rstrip() + "\n")
    (HERE / "notebooks/inspect_results.html").write_text(render_preview(notebook, sections))
    outputs = ["notebooks/inspect_results.ipynb", "notebooks/inspect_results.py", "notebooks/inspect_results.html"]
    outputs += [str(p.relative_to(HERE)) for p in sorted((HERE / "data/inspection").iterdir())]
    manifest = dict(revision=REVISION, sources=hashes,
                    outputs={p: digest((HERE / p).read_bytes()) for p in outputs},
                    simulationExecuted=False, originalNotebookExecuted=False, uploadExecuted=False,
                    codeCellsExecuted=5, savedImages=6, newPlots=1, missingMetricEntries=9,
                    sections=sections)
    (HERE / "data/python-inspection-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    action = "Executed" if execute else "Checked and rendered saved"
    print(f"{action} inspection notebook: 5 cells, 6 original figures, 1 scalar plot; SHA256 {manifest['outputs']['notebooks/inspect_results.ipynb']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Explicitly run only the new lightweight inspection in an isolated kernel")
    build(execute=parser.parse_args().execute)
