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
