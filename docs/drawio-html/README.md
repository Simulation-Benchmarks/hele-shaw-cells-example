# From Validation.drawio to an HTML viewer

This folder is a portable copy of the Hele-Shaw semantic drawing, its clickable HTML viewer, and the records connecting diagram elements to URLs. Copy the **whole folder** to keep the viewer working.

The drawing is not reconstructed from the semantic dataset. The original draw.io XML is rendered by the official draw.io viewer into SVG, which is displayed inside `index.html`. Hyperlinks are added separately, without changing the original labels, colours, coordinates, arrow directions, or routing points.

## Open and rebuild

Open `index.html` in an ordinary browser. The included JavaScript, styles, and renderer are local; rendering this diagram does not need an internet connection. Following links to the published atlas, GitHub, or ontology documentation does need one.

If your browser restricts local files, run this command **inside this folder**:

```sh
python3 -m http.server 8765 --bind 127.0.0.1
```

Then open [http://127.0.0.1:8765/](http://127.0.0.1:8765/). Stop the server with Ctrl+C when finished.

After changing a link, rebuild and check the package:

```sh
python3 build.py
python3 build.py --check
```

The builder uses only Python 3's standard library. It generates `data.js`, `Validation.linked.drawio`, `mapping.csv`, and `manifest.json`. It does not alter `Validation.drawio`, run a simulation, or infer scientific relationships.

## What belongs to what

| File | Purpose |
| --- | --- |
| `Validation.drawio` | Unchanged original drawing; authoritative for appearance and original cell data. |
| `index.html` | Browser page hosting the diagram and controls. |
| `drawio-links.json` | Editable link records, keyed by original cell ID; contains the upstream `{meta, links}` structure. |
| `diagram-crosswalk.json` | Preserved mapping from original cells to semantic entities and relationships. |
| `mapping.csv` | Readable inventory of all 212 graphical cells and their mappings. Generated. |
| `data.js` | Exact source XML and resolved link records in `window.HELE_SHAW_DRAWIO`. Generated. |
| `Validation.linked.drawio` | A separate draw.io file with native hyperlink metadata. Generated. |
| `manifest.json` | Package verification information. Generated. |
| `build.py` | Standalone builder and consistency checker. |
| `drawio-viewer.js` | Unchanged atlas adapter around the official renderer. |
| `viewer.js`, `style.css`, `tokens.css` | Viewer controls, cell details, and presentation; tokens are copied from the atlas. |
| `vendor/drawio/29.6.6/` | Pinned official renderer, offline configuration, provenance, and license notices. |

There are **112 vertices and 100 edges: 212 graphical cells**. The XML contains 214 `mxCell` elements because the root and layer are structural cells, not displayed entities or relationships.

## How rendering works

1. `build.py` reads the original XML and checks it against the pinned source hash and mapping records.
2. It keeps the XML text intact in `data.js`. Every graphical cell receives a separate URL record using its original `mxCell` ID.
3. The page loads the offline configuration, unchanged official draw.io 29.6.6 renderer, adapter, and viewer controls in order.
4. The adapter passes the XML to draw.io's `GraphViewer` and uses its native SVG export. The official renderer draws the shapes, HTML labels, and arrows.
5. The adapter adds hyperlinks and nonvisual accessibility and audit attributes. It compares the visible SVG structure before and after adding links and rejects a change in appearance or an omitted source cell.

The browser SVG retains `data-cell-id` and adds `data-drawio-id`. These attributes connect a visible shape or arrow back to the XML and JSON records. CSS for the page must not override the diagram's own shape, text, or colour styles.

## Two concrete mappings

The original **Model** vertex has this identity:

| Layer | Value |
| --- | --- |
| XML `mxCell` ID | `JDZ3WXQOoo0OTXsIz6hO-6` |
| Original label | `Model` |
| Semantic `entityId` | `model` |
| Link record key | `links["JDZ3WXQOoo0OTXsIz6hO-6"]` |
| Atlas route | `#overview/model` |
| Portable URL | `https://simulation-benchmarks.github.io/hele-shaw-cells-example/#overview/model` |

Equal labels do not imply equal identities. Two boxes with the same text retain their separate original cell IDs and mapping records.

An arrow illustrates the difference between the drawing and its semantic interpretation:

| Field | Original drawing | Semantic mapping |
| --- | --- | --- |
| Arrow ID | `eiFgZNk86BmHCPwQhzBy-49` | Same `diagramId` |
| Label | `part of` | `has part` |
| Direction | `validation metrics` (`…-43`) → `dataset` (`…-44`) | `dataset` (`…-44`) → `validation metrics` (`…-43`) |

Its record retains `sourceDiagramId`, `targetDiagramId`, and `originalValue`, while `mappedSource`, `mappedTarget`, `normalizedLabel`, and `directionNormalized: true` describe the separate interpretation. **The HTML drawing still shows the original arrow and label.** Its URL opens the atlas's explanation at `#relationship/eiFgZNk86BmHCPwQhzBy-49`.

Other arrows have `asserted: false`, a `Proposed` status, and a `reviewNote`. Those records identify unresolved interpretations; a clickable link does not establish scientific validity. Original spelling is also retained, even when a normalized display label or suggested term is recorded separately.

## Change a destination

Edit the relevant entry's `url` or `target` in `drawio-links.json`, then run the rebuild and check commands above. For example, the existing Model entry includes:

```json
{
  "diagramId": "JDZ3WXQOoo0OTXsIz6hO-6",
  "entityId": "model",
  "url": "#overview/model",
  "target": "_self"
}
```

This is an excerpt; retain the other fields in the actual file. `_self` opens in the current tab; `_blank` requests a new tab. A fragment such as `#overview/model` or a relative path such as `notebooks/Simulation_Walkthrough.html#inspect-results` is resolved against `meta.publishedBaseUrl`. Generated browser links are absolute URLs, so copying this folder does not break links to atlas pages. Do not edit `data.js` or `mapping.csv` by hand; rebuilding replaces them.

Source labels, IDs, and edge endpoints must continue to match the original and crosswalk. The original is pinned to SHA-256:

```text
182b574888e044685ed66d6505eed993ff3187d04fa58af9ade6e0c98b93f1ab
```

Replacing the drawing is a separate review task: update its crosswalk, link inventory, source hash, and verification together. Changing the hash alone does not establish a correct mapping. This package supports this single-page, uncompressed, `math="0"` drawing with standard shapes and no external assets; it is not a general converter for arbitrary `.drawio` files.

`Validation.linked.drawio` uses draw.io's native `UserObject` wrappers. A cell's ID and value move into equivalent wrapper `id` and `label` attributes, together with the URL. Removing those wrappers and restoring the attributes recovers the original XML structure. The original file itself stays unchanged.

## Refresh from the repository

From the repository root, refresh this snapshot with:

```sh
python3 docs/semantic/tools/export_drawio_package.py
```

The complete semantic-site build also exports this folder. **Exporting replaces the snapshot's drawing, link records, crosswalk, and canonical viewer assets.** Save independent link edits elsewhere before an export, or make the corresponding change in the atlas source mapping first. The atlas's maintained pipeline is `build_model.py` → `build_drawio.py` → package export.

## Troubleshooting and provenance

- **Blank diagram:** copy the entire folder, enable JavaScript, and try the local server above. The renderer, offline configuration, adapter, and `data.js` must all load.
- **Old destination after an edit:** rebuild, run `--check`, then reload the page.
- **Hash, missing-cell, or mapping error:** restore the matching source and mapping snapshot. Do not suppress the check or regenerate IDs to make it pass.
- **Link unavailable offline:** the drawing is local; the linked atlas and evidence pages are external destinations.
- **Compressed XML, mathematical typesetting, or external assets:** these require explicit support and dependency review before replacing this example. The offline adapter rejects math-enabled input.

The renderer comes unchanged from [draw.io Desktop 29.6.6](https://github.com/jgraph/drawio-desktop/releases/tag/v29.6.6). The native wrapper format is documented in [draw.io's file-format notes](https://github.com/jgraph/drawio/wiki/File-Format#user-objects). See [renderer provenance and licensing](vendor/drawio/29.6.6/README.md) and retain all bundled license notices when distributing this folder. The atlas adapter carries its own MIT notice; the official draw.io renderer and its bundled dependencies retain their respective licenses.
