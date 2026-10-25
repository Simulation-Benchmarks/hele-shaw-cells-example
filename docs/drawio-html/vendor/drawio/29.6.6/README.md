# Official draw.io static renderer

`viewer-static.min.js` is copied without modification from draw.io Desktop 29.6.6
for macOS, specifically its offline Quick Look preview extension. Its exact
source path, byte length and SHA-256 digest are recorded in `provenance.json`.

The original diagram is rendered by draw.io's `GraphViewer` and exported by its
native `Graph.getSvg` / `Graph.createSvgImageExport` implementation. The atlas
adapter adds hyperlinks and nonvisual audit metadata; it does not draw shapes,
reconstruct edge routes, substitute labels, or rewrite the source XML.

Upstream: https://github.com/jgraph/drawio-desktop/releases/tag/v29.6.6

## Licenses and notices

- draw.io and mxGraph: Apache License 2.0; see `LICENSE` and the retained
  `SHAPES-LICENSE` / `STENCILS-LICENSE` notices.
- DOMPurify 3.3.2: copyright Cure53 and other contributors; the original bundle
  retains its Apache-2.0 / MPL-2.0 notice. This distribution uses Apache-2.0.
- pako 2.1.0: MIT and Zlib; see `PAKO-LICENSE`, `PAKO-ZLIB-NOTICE` and the bundle's
  retained license notice.
- spin.js 2.0.0: copyright 2011–2014 Felix Gnass, MIT; see `SPIN-LICENSE`.

## Offline behavior

The static bundle contains the viewer and built-in shape definitions. This
`Validation.drawio` uses standard shapes, no external images or fonts, and
`math="0"`. The official bundle nevertheless initializes MathJax at startup.
Load the separately authored `offline-config.js` before it: this uses the native
loader's existing-MathJax guard to disable that unused optional loader. The atlas
adapter explicitly rejects math-enabled diagrams while the sentinel is active.
Rendering this source then requires no remote requests. The bundle retains its
upstream default URLs for optional external images, math and assets. New diagrams
using those features require a separate dependency review; the bundle has not
been modified to rewrite or suppress their behavior.

The application loads `offline-config.js`, then the renderer, then
`drawio-viewer.js`, in that order. The adapter
exports `HeleShawDrawio.render({xml, links})` and
`HeleShawDrawio.mount(container, {xml, links, onNavigate})`. `links` is keyed by
original cell ID; values are URLs or `{url, target, entityId, label}` objects.
Rendering returns an SVG element, dimensions, complete source-cell inventory,
and an audit comparing official SVG appearance before and after link augmentation.

No toolbar, editor, remote iframe, or graph-layout algorithm is used. The atlas
continues to own pan/zoom. Do not apply atlas node palettes, fonts, or SVG shape
rules to `.drawio-original`; its original draw.io styles are authoritative.
