---
version: alpha
name: Hele-Shaw semantic atlas
description: A diagram-first atlas connecting the validation model to repository workflows and evidence.
colors:
  ink: "#182f3a"
  muted: "#546872"
  primary: "#245a8d"
  science: "#246952"
  literature: "#72568e"
  config: "#846114"
  warning: "#8b4c28"
  background: "#ffffff"
  surface: "#ffffff"
  border: "#d6e0e3"
  science-tint: "#edf5f0"
  code-tint: "#edf2f9"
  warning-tint: "#fcf2e7"
  scrollbar: "#93a5ae"
  scrollbar-track: "#f3f6f7"
  scrollbar-hover: "#738c99"
  scrollbar-active: "#546872"
typography:
  display:
    fontFamily: "Arial, Helvetica, sans-serif"
  body:
    fontFamily: "Arial, Helvetica, sans-serif"
  mono:
    fontFamily: "'SFMono-Regular', Consolas, monospace"
omitted:
  - section: spacing
    reason: Inherited geometry is implemented once in style.css.
  - section: rounded
    reason: Component-specific corner treatment is documented in Shapes.
  - section: components
    reason: Native HTML components share the owners documented below.
---

# Hele-Shaw semantic atlas

## Overview

Preserve the FAIR4SD semantic atlas design: the diagram is the interface.
Researchers and engineering students follow the validation model into actual
repository workflows and evidence. The supplied `Validation.drawio` is the
scientific structure; it is preserved byte-for-byte. Complete experimental and
validation branches remain visible even when the repository does not implement
them. This is an English scientific content explorer, with no account, remote
mutation, simulation execution, or uploads in the browser.

Design adapted from the FAIR-systemDynamics/fair-hunter-prey-simulation
`DESIGN.md`, © 2026 Vasiliy Seibert, CC BY 4.0. Viewer and rendering code retain
their MIT attribution. Hele-Shaw content is generated independently.

## Colors

White canvas, dark readable labels, pastel category fills, thin borders.
Category colors retain FAIR4SD's semantic roles: blue model, white numerical
variables, pale blue files/datasets, green processing steps, orange methods,
yellow tools/configurations, and purple fields/bindings. `tools/build_graphs.py`
owns the graph palette and generates each graph's matching legend. Status is
written in node labels and descriptions, not communicated through color alone.
Conceptual steps and proposed relationships are explicitly qualified.

The token path is this frontmatter → `tools/build_tokens.py` → `tokens.css` →
`style.css`. Do not hand-edit generated tokens or introduce another theme.

## Typography

Arial/Helvetica for all interface and diagram text; local monospace for code.
Retain the reference type scale, with 16px native graph labels and smaller
ontology captions. Graph labels zoom with their nodes; hover/focus descriptions
retain readable screen-sized text. No remote fonts or rendering dependencies.

## Layout

The compact repository header has three bookmarkable navigation links:
Semantic Model (`#overview`), Workflows (`#workflows`) and NFDI4Ing Use Cases
(`#nfdi4ing`). The header wraps at the reference breakpoints; `--header-height`
controls canvas offsets and document anchor clearance.

Semantic Model is a full-window pan/zoom canvas with a small caption, floating
legend and zoom controls, and no permanent inspector. A curated overview shows
the experimental and simulation branches converging on validation. Model,
configuration and dataset details open related-entity views. Search reaches
every entity, including the complete supplied diagram's detail views.

Workflows is a naturally scrolling document with contents and four sections:
prepare/simulate, inspect results, check reproducibility, package/share. Each
has an action-sentence title, evidence note, artifact links and five numbered
stages. Stage numbers encode reading order; arrows retain relationship direction.
Inline diagrams scroll horizontally at narrow widths. Explore diagram opens
the shared canvas; Back to workflows restores the originating section.

NFDI4Ing Use Cases uses the reference two-column service/workflow pairs with
pale-blue service columns, stacking on phones. Service status appears before
workflow links. Jupyter has no configured project launch; ROHub upload remains
optional and unverified. The saved notebook is a continuous document with
heading links, exact saved outputs and collapsible long logs.

## Elevation & Depth

Flat canvas and document surfaces. Only search suggestions and hover/focus
descriptions use a restrained shadow. No decorative gradients or animation.

## Shapes

Pastel rounded rectangular nodes, labeled directional arrows and small rounded
native controls. Methods, tools, processing steps and artifacts remain distinct.
Graph layouts are generated from the semantic dataset; neighborhood routing uses
Graphviz. Conceptual status must stay legible without hovering.

## Components

| Capability | Canonical owner | Contract |
|---|---|---|
| Navigation | index.html + app.js | Three hash routes, contextual entity routes, Back/refresh, descriptive titles |
| Search | app.js | Local search, clear button, keyboard traversal, Escape, no-results feedback |
| Canvas and inline diagrams | app.js bindGraph | Shared node behavior, unique SVG IDs, pan/zoom/fit, keyboard panning |
| Graph generation | tools/build_graphs.py | Deterministic entity IDs, RDF-backed arrows, visible evidence status |
| Workflow catalog | app.js + model.workflows | Contents, section anchors, five stages, contextual return links |
| Service catalog | app.js + nfdi4ing-services.json | Service status, existing workflow references, responsive pairs |
| Notebook | tools/notebook_view.py | Saved content only; section anchors, source links, output fidelity |
| Scrollbars | style.css | Global thumb/track/hover/active and forced-colors behavior |

Native anchors navigate; native buttons zoom or clear search. File/software
nodes open evidence sources; conceptual entities explore connections. The
selected entity is encoded in the URL; draft search text is transient. Diagram
neighborhoods disclose omitted neighbors while RDF retains every relationship.
Use visible focus, accessible names, hover/focus descriptions, non-drag panning,
reduced-motion support and readable contrast. Document views own natural page
scrolling; the canvas's viewport constraint never applies to them.

## Do's and Don'ts

- Preserve the reference layout, type, color and interaction vocabulary.
- Link actual source revisions, parameter selectors and saved notebook sections.
- Treat baseline regression and experimental validation as different activities.
- Keep missing values and saved failures visible; never substitute baseline data.
- Explain the diagram-to-implementation mapping without claiming the existing
  RO-Crate writer already emits the complete ontology model.
- Do not change simulation code or enable expensive execution in site builds.
