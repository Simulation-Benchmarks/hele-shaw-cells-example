# Verification — 25 October 2026

- Static build succeeds without running notebooks, simulations or uploads.
- 30 semantic checks pass: 4,830 RDF triples, equivalent Turtle/JSON-LD, SHACL
  with negative cases, complete 112-vertex/100-edge diagram crosswalk, pinned
  source hashes, parameter bindings, workflow connectivity and 251 SVG views.
- Seven automated tests pass: saved-notebook fidelity and deliberate tampering
  cases, local assets, workflow actions and notebook section destinations.
- Saved evidence retains 15 code cells, 47 outputs, nine output figures and two
  tables; 36 equations render as local MathML. The original notebook is unchanged.
- Design-document validation and the strict UI audit pass with no errors or
  warnings; JavaScript syntax and Git whitespace checks pass.
- Browser checks cover the three tabs, service-to-workflow links, full-diagram
  and contextual return links, browser Back/refresh, keyboard search and clear,
  no-results feedback, Escape, visible focus, accessible SVG links, pointer and
  arrow-key panning, zoom and Fit.
- Desktop (1280 × 800) and narrow (390 × 844) layouts checked. Narrow documents
  have no horizontal page overflow; wide diagrams scroll within their regions,
  including by keyboard. Notebook section links clear the sticky header.
- Missing-data fixture displays an explanation and a direct RDF source link.
  Controls that depend on the dataset are disabled.
- Rendering assets have no external scripts or fonts. Direct `file://` testing
  was blocked by the browser URL policy; HTTP preview rendering was verified.
- `Validation.drawio` and its published copy have the same SHA-256:
  `182b574888e044685ed66d6505eed993ff3187d04fa58af9ade6e0c98b93f1ab`.

These checks validate the atlas representation and saved evidence. They do not
certify the scientific model or establish experimental validation, a new solver
run, a working project-specific Jupyter launch, or a successful ROHub upload.


## Exact original drawing follow-up — 2026-10-25

The main Semantic Model canvas now uses the official, unmodified draw.io 29.6.6
static renderer on the byte-identical original XML. All 112 vertices and 100
relationships render, including the configuration and dataset views and original
legend. Every original cell has a source, concept or relationship link.

The native SVG visual structure is compared before and after hyperlink injection
at runtime; browser inspection reported `visualUnchanged: true`, 212 rendered
cells and 212 linked cells (visual signature `fnv1a32:642050a5`). The original
SHA-256 remains `182b574888e044685ed66d6505eed993ff3187d04fa58af9ade6e0c98b93f1ab`.
The linked `.drawio` derivative normalizes losslessly to the original tree,
including labels, styles, geometry, nested waypoints, ordering and endpoints.

The build checks 30 semantic invariants plus the exact-drawing validator. All 22
unit tests pass, including 15 original-drawing and offline-renderer checks.
The official bundle hash/size and required local script order are checked. The
unused default remote MathJax startup is disabled; the source has `math="0"`.
Browser DOM inspection after a fresh reload found no remote rendering assets.

Browser verification covered desktop (1280×800) and mobile (390×844), complete
cell coverage, visual comparison before/after links, native label clicks and
keyboard Enter, uncertain relationship notes, the preserved original vs.
normalized `part of` direction, search and return to the original drawing,
zoom/Fit, Back/refresh, and all three tabs. No page horizontal overflow was found.
Workflow, service and saved-notebook content are unchanged. The original diagram
retains its exact labels; conceptual status is disclosed by the canvas note,
focus/hover descriptions and linked relationship details.

The strict UI audit reports no findings for the edited interface sources.
Generated data and unchanged third-party code are excluded from that UI scan.
Whitespace checks pass for authored changes; two upstream whitespace-only lines
in the official viewer are retained to preserve its verified byte-for-byte hash.


## Executable NFDI4Ing workflow — 2026-10-25

The inspection workflow now has five numbered notebook stages, linked to an
actual authenticated NFDI4Ing JupyterLab destination. Service use cases follow
FAIR4SD’s “Use the service to [user action]” formulation. The Jupyter case has a
direct notebook action, setup guide, workflow link and saved reading alternative.
All four workflow slugs remain available.

A fresh repository clone was created in the authenticated service's persistent
work folder. The source notebook checksum matched the committed notebook before
execution. JupyterLab Run All Cells completed with prompts 1–5, no error outputs
and an Idle kernel. Python 3.13.11, NumPy 2.3.5, Pandas 2.3.3 and Matplotlib 3.10.8
were observed. No Docker, OpenFOAM, original-notebook execution or upload ran.
The inspection preserved nine missing measurements, reproduced all 21 recorded
comparison decisions, redisplayed six original images, and created one plot from
recorded scalar values. Runtime evidence and source identity are in
`jupyter-validation.json`; no account identifier or credential is published.

The public user-redirect URL and all five heading links were checked in the same
workspace and browser tab. The Hub may initially scroll a long section past its
heading in a narrow panel; the regression heading was verified with the notebook
expanded by collapsing the file browser. This behavior and the two-step Back
navigation through the Hub redirect are recorded in the setup/evidence files.
The site’s own section links, Back navigation and refresh were also checked.

The full static build passes 41 semantic checks plus original-drawing validation;
all 38 unit tests pass. The strict audit of authored interface sources reports no
findings. Desktop (1280×800) and mobile (390×844) checks show no page overflow;
workflow diagrams scroll locally and all seven inspection figures load. The
original drawing still renders all 212 elements with unchanged visual signature
`fnv1a32:642050a5`. FAIR4SD, the original diagram and the historic walkthrough
remain unchanged. Normal publication builds render saved outputs without
executing any notebook.
