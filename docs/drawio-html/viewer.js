// SPDX-FileCopyrightText: 2026 Vasiliy Seibert
// SPDX-License-Identifier: MIT
// The shared adapter renders the drawing. This file only owns the page controls.
(() => {
  'use strict';
  const drawing = document.getElementById('drawing');
  const status = document.getElementById('status');
  const buttons = [...document.querySelectorAll('.zoom button')];
  try {
    const payload = window.HELE_SHAW_DRAWIO;
    const result = window.HeleShawDrawio.mount(document.getElementById('diagram'), payload);
    let scale = 1;
    let fitted = true;
    const fitScale = () => Math.min(1, (drawing.clientWidth - 28) / result.width,
      (drawing.clientHeight - 28) / result.height);
    const zoom = (next, fit = false) => {
      fitted = fit;
      scale = Math.max(0.05, Math.min(4, next));
      result.svg.style.width = `${result.width * scale}px`;
      result.svg.style.height = `${result.height * scale}px`;
      status.textContent = `${result.vertexCount} shapes · ${result.edgeCount} arrows · ${Math.round(scale * 100)}%`;
      document.getElementById('zoom-out').disabled = scale <= 0.05;
      document.getElementById('zoom-in').disabled = scale >= 4;
      if (fit) { drawing.scrollLeft = 0; drawing.scrollTop = 0; }
    };
    buttons.forEach(button => { button.disabled = false; });
    document.getElementById('zoom-in').addEventListener('click', () => zoom(scale * 1.3));
    document.getElementById('zoom-out').addEventListener('click', () => zoom(scale / 1.3));
    document.getElementById('fit').addEventListener('click', () => zoom(fitScale(), true));
    document.getElementById('actual').addEventListener('click', () => zoom(1));
    new ResizeObserver(() => { if (fitted) zoom(fitScale(), true); }).observe(drawing);
    zoom(fitScale(), true);
    const inspect = event => {
      const anchor = event.target.closest('a[data-drawio-id]');
      if (!anchor) return;
      const id = anchor.dataset.drawioId;
      const entry = payload.links[id];
      if (!entry) return;
      const pairs = [['Original cell ID', id], ['Original label', entry.originalLabel || '(unlabelled arrow)'],
        ['Mapping status', entry.status], ['Semantic entity', entry.entityId],
        ['Original endpoints', entry.type === 'edge' ? `${entry.sourceDiagramId} → ${entry.targetDiagramId}` : null],
        ['Meaning', entry.definition || entry.reviewNote], ['Destination', entry.url]];
      const list = document.getElementById('cell-details');
      list.replaceChildren();
      for (const [label, value] of pairs) {
        if (value == null) continue;
        const term = document.createElement('dt'), detail = document.createElement('dd');
        term.textContent = label;
        if (label === 'Destination') {
          const link = document.createElement('a');
          link.href = value; link.textContent = value; link.target = entry.target;
          link.rel = 'noopener noreferrer'; detail.append(link);
        } else { detail.textContent = value; }
        list.append(term, detail);
      }
      list.hidden = false;
      document.getElementById('cell-hint').hidden = true;
    };
    result.svg.addEventListener('mouseover', inspect);
    result.svg.addEventListener('focusin', inspect);
    document.getElementById('audit').textContent = `Rendering check: ${result.audit.renderedCellCount} of ${result.audit.sourceCellCount} cells rendered; ${result.audit.linkCount} links; appearance unchanged after adding links. Source SHA-256: ${payload.meta.sourceSha256}.`;
  } catch (error) {
    buttons.forEach(button => { button.disabled = true; });
    status.textContent = `Drawing could not load: ${error.message} Keep the complete folder together, rebuild with python3 build.py, then reload this page.`;
  }
})();
