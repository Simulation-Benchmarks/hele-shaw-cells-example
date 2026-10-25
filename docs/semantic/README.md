# Hele-Shaw semantic atlas

[Open the atlas](https://simulation-benchmarks.github.io/hele-shaw-cells-example/).
Three views connect the **Semantic Model**, **Workflows**, and **NFDI4Ing Use Cases**.
The static viewer preserves FAIR4SD's white canvas, pastel nodes, typography,
source links, search and pan/zoom interactions. See `ATTRIBUTION.md` and the
repository's `DESIGN.md`.

## Evidence and scientific scope

The complete supplied `Validation.drawio` is retained unchanged. Its 112 vertices
and 100 arrows have a machine-readable crosswalk, including original labels,
identifiers and uncertain relationships. The overview is curated for readability;
entity search and neighborhood views expose the detailed model. Dashed arrows
identify proposed interpretations, not established assertions.

The experimental branch and experiment-versus-simulation validation remain
conceptual. The repository implements simulation preparation, OpenFOAM execution,
field/log post-processing, regression checks and local RO-Crate packaging. Finger
metrics use simulation fields directly; the diagram's image-processing branch is
also represented. Regression against a simulation baseline is not experimental
validation. The existing RO-Crate writer's Method/PropertyValue representation is
documented separately from this atlas's richer conceptual model.

Source files are read from revision
`8ec1b34f0a8fdbc103f35f88cba20e12b465800b`. Source hashes and JSON parameter selectors
are checked on every build. Parameter files and code take precedence over stale
descriptive prose; `source/` records the evidence and diagram mappings. The graph
uses verified Metadata4Ing terms and explicitly declared local `hs:` extensions.
Vocabulary normalization is not a claim of scientific certification.

Four workflows have five illustrated stages each:

1. Prepare and simulate the reference, mesh-refinement and doubled-flow cases.
2. Extract and inspect fields, metrics, figures and saved notebook evidence.
3. Check reproducibility against the configuration-1 baseline and tolerances.
4. Package results as a research object and explore optional ROHub sharing.

The notebook reading view preserves all 15 code cells, 47 outputs, nine saved
figures and two tables. It renders equations as offline MathML and does not start
a kernel. It is a saved run, not a new clean execution: missing metrics remain
missing, and comparisons of configurations 2/3 with the configuration-1 baseline
retain their reported failures. The reference image is a simulation image, not an
experimental photograph. The ROHub notebook is not presented as an executed or
verified upload; the site links to repository guidance instead. A project-specific
NFDI4Ing Jupyter Hub launch has not been configured.

## Navigation

Hover or keyboard-focus nodes for definitions and evidence status. Scientific
concepts open related entities; concrete artifacts and software open source
evidence. Search opens an entity's neighborhood. A neighborhood shows up to 28
neighbors and reports omitted connections; RDF retains the full model.

Drag or use arrow keys to pan the canvas; use the wheel, +/− or Fit to zoom.
Workflows and use cases scroll as documents. Wide inline diagrams scroll locally.
Workflow headings, full diagrams, entities and saved notebook sections have
stable links, and browser Back returns to the previous view.

## Build and validate

Use Python 3.12 and Graphviz (`dot` on PATH). Dependencies are for static rendering
and semantic validation only:

```sh
python -m pip install -r docs/semantic/requirements.txt
python docs/semantic/tools/build_site.py --output-dir _site
python -m unittest discover -s docs/semantic/tests -p 'test_*.py'
python -m http.server 8765 --bind 127.0.0.1 --directory _site
```

The builder renders the saved notebook, builds RDF/browser data, generates CSS
tokens and SVG diagrams, validates the results and copies the publishable files
into `_site`. It never runs simulations or uploads. To update the inspected source
revision, change the explicit revision in both model and notebook builders and
review all affected evidence before regenerating.

Generated artifacts are committed for direct offline use. `model.ttl` and
`model.jsonld` are equivalent graphs; `vocabulary.ttl` defines the local extension;
`shapes.ttl` is the application validation profile. `data/model.json` and its JS
counterpart supply entities, edges, overview, workflows and services.
`data/graphs.js` supplies precomputed SVGs. Validation checks representation and
evidence integrity, not the scientific validity of the simulation.

## Publication

The independent `.github/workflows/pages.yml` builds preview artifacts for pull
requests and publishes to GitHub Pages from `main`. Pages uses GitHub Actions as
its publishing source. Site publication leaves the manual benchmark workflow
unchanged. No credentials or upload functions are included in the published UI.
