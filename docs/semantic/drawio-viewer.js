// SPDX-FileCopyrightText: 2026 Vasiliy Seibert
// SPDX-License-Identifier: MIT
// Adapter only. All diagram painting is performed by the unchanged draw.io viewer.
(() => {
  'use strict';
  const VERSION = '29.6.6';
  const SVG_NS = 'http://www.w3.org/2000/svg';
  const XLINK_NS = 'http://www.w3.org/1999/xlink';

  function linkFor(links, id) {
    const value = links instanceof Map ? links.get(id) : links[id];
    if (!value) return null;
    const link = typeof value === 'string' ? {url: value} : value;
    const url = link.url || link.href;
    if (!url || /^\s*(?:javascript|data|vbscript):/i.test(url)) return null;
    return {...link, url, target: link.target || (url.startsWith('#') ? '_self' : '_blank')};
  }

  function stableIds(svg) {
    const replacements = new Map();
    [...svg.querySelectorAll('[id]')].forEach((element, index) => {
      replacements.set(element.id, `hele-shaw-drawio-svg-${index}`);
    });
    for (const element of [svg, ...svg.querySelectorAll('*')]) {
      for (const attribute of [...element.attributes]) {
        let value = attribute.value.replace(/url\(#([^)]+)\)/g,
          (_, id) => `url(#${replacements.get(id) || id})`);
        if ((attribute.localName === 'href') && value.startsWith('#') && replacements.has(value.slice(1))) {
          value = '#' + replacements.get(value.slice(1));
        }
        if (value !== attribute.value) element.setAttributeNS(attribute.namespaceURI, attribute.name, value);
      }
      if (element.id && replacements.has(element.id)) element.id = replacements.get(element.id);
    }
    return svg;
  }

  // Navigation wrappers and audit metadata do not contribute to visible ink.
  // Keep every shape, text/HTML label, transform, colour and geometry attribute.
  function visualStructure(node) {
    if (node.nodeType === Node.TEXT_NODE) return node.nodeValue;
    if (node.nodeType !== Node.ELEMENT_NODE || ['title', 'desc'].includes(node.localName)) return '';
    const children = [...node.childNodes].map(visualStructure).join('');
    if (node.localName === 'a') return children;
    const attributes = [...node.attributes]
      .filter(attribute => !/^(?:data-|aria-)/.test(attribute.name)
        && !['role', 'tabindex', 'focusable'].includes(attribute.name))
      .map(attribute => [attribute.name, attribute.value]).sort((a, b) => a[0].localeCompare(b[0]));
    return JSON.stringify([node.namespaceURI, node.localName, attributes]) + children + '/';
  }

  function fingerprint(value) {
    let hash = 2166136261;
    for (let index = 0; index < value.length; index++) hash = Math.imul(hash ^ value.charCodeAt(index), 16777619);
    return 'fnv1a32:' + (hash >>> 0).toString(16).padStart(8, '0');
  }

  /**
   * Render original draw.io XML synchronously with the official renderer.
   * links: object/Map keyed by original mxCell ID; value is a URL or
   * {url|href, target?, entityId?, label?}. The source XML is never modified.
   * Returns {svg,width,height,cells,vertexCount,edgeCount,audit,rendererVersion}.
   * The detached SVG is ready for the atlas's existing pan/zoom container.
   */
  function render(options = {}) {
    const defaults = window.HELE_SHAW_DRAWIO || {};
    const xml = options.xml || defaults.xml;
    const links = options.links || defaults.links || {};
    if (typeof xml !== 'string' || !xml.trim()) throw new Error('The original draw.io diagram is unavailable.');
    if (typeof window.GraphViewer !== 'function') throw new Error('The official draw.io renderer could not load.');
    const documentXml = new DOMParser().parseFromString(xml, 'application/xml');
    if (documentXml.querySelector('parsererror')) throw new Error('The original draw.io XML is invalid.');
    if (window.MathJax?.heleShawDisabled && (documentXml.querySelector('mxGraphModel[math="1"]') || window.urlParams?.math === '1')) {
      throw new Error('This diagram requires mathematical typesetting, which is not included in the offline viewer.');
    }
    const sourceCells = new Map([...documentXml.querySelectorAll('mxCell[vertex="1"],mxCell[edge="1"]')]
      .map(cell => [cell.getAttribute('id'), cell]));
    if (!sourceCells.size) throw new Error('The diagram has no uncompressed source cells to render.');

    // Native HTML labels require an attached, measurable host. This host is
    // outside the semantic-graph CSS class so atlas styles cannot repaint it.
    const host = document.createElement('div');
    host.setAttribute('aria-hidden', 'true');
    host.style.cssText = 'position:fixed;left:-20000px;top:0;width:4096px;height:4096px;visibility:hidden;overflow:hidden;';
    document.body.appendChild(host);
    let viewer;
    try {
      viewer = new GraphViewer(host, documentXml.documentElement, {
        toolbar: '', nav: false, lightbox: false, edit: null, highlight: 'none',
        'auto-fit': false, 'auto-crop': false, 'auto-origin': false,
        center: false, resize: false, responsive: false, 'dark-mode': false,
        'show-link-icons': false, 'show-tooltip-icons': false
      });
      const graph = viewer.graph;
      if (!graph) throw new Error('The official draw.io viewer did not initialize.');
      graph.view.scaleAndTranslate(1, 0, 0);
      graph.view.validate();
      const exportSvg = () => stableIds(graph.getSvg(
        graph.background || null, 1, 0, false, true, true, true,
        graph.createSvgImageExport(true), null, false, false, null, 'diagram'
      ));
      const originalSvg = exportSvg();
      const originalVisual = visualStructure(originalSvg);
      const originalGetLink = graph.getLinkForCell.bind(graph);
      const originalGetTarget = graph.getLinkTargetForCell.bind(graph);
      graph.getLinkForCell = cell => linkFor(links, cell.id)?.url || originalGetLink(cell);
      graph.getLinkTargetForCell = cell => linkFor(links, cell.id)?.target || originalGetTarget(cell);
      const svg = exportSvg();
      const linkedVisual = visualStructure(svg);
      if (originalVisual !== linkedVisual) throw new Error('Link augmentation changed the official SVG rendering.');

      const seen = new Set(), cells = [];
      for (const group of svg.querySelectorAll('[data-cell-id]')) {
        const id = group.getAttribute('data-cell-id');
        const source = sourceCells.get(id);
        if (!source) continue; // Native root and layer groups are not entities.
        if (seen.has(id)) throw new Error(`The renderer duplicated source cell ${id}.`);
        seen.add(id);
        const kind = source.getAttribute('edge') === '1' ? 'edge' : 'vertex';
        const link = linkFor(links, id);
        group.setAttribute('data-drawio-id', id);
        group.setAttribute('data-drawio-kind', kind);
        group.setAttribute('data-drawio-type', kind);
        group.classList.add('drawio-cell', 'drawio-' + kind);
        if (kind === 'edge') {
          group.setAttribute('data-drawio-source', source.getAttribute('source') || '');
          group.setAttribute('data-drawio-target', source.getAttribute('target') || '');
        }
        if (link?.entityId) group.setAttribute('data-entity', link.entityId);
        const anchors = [...group.querySelectorAll('a')].filter(anchor => anchor.closest('[data-cell-id]') === group);
        if (link && !anchors.length) throw new Error(`The renderer omitted the link for source cell ${id}.`);
        for (const anchor of anchors) {
          if (!link) continue;
          anchor.setAttribute('href', link.url);
          anchor.setAttributeNS(XLINK_NS, 'xlink:href', link.url);
          anchor.setAttribute('target', link.target);
          anchor.setAttribute('rel', 'noopener noreferrer');
          anchor.setAttribute('tabindex', '0');
          anchor.setAttribute('role', 'link');
          anchor.setAttribute('data-drawio-id', id);
          anchor.setAttribute('data-drawio-kind', kind);
          if (link.entityId) anchor.setAttribute('data-entity', link.entityId);
          anchor.setAttribute('aria-label', link.label || graph.convertValueToString(graph.model.getCell(id)) || `Diagram ${kind}`);
        }
        cells.push({id, kind, source: source.getAttribute('source'), target: source.getAttribute('target'),
          parent: source.getAttribute('parent'), value: source.getAttribute('value'),
          style: source.getAttribute('style'), linked: Boolean(link)});
      }
      const missing = [...sourceCells.keys()].filter(id => !seen.has(id));
      if (missing.length) throw new Error(`The official renderer omitted source cells: ${missing.join(', ')}`);
      // draw.io's SVG export includes a browser-compatibility warning link in
      // its foreignObject fallback. It is not one of the diagram's cells.
      // Preserve the native fallback pixels but keep it out of diagram tabbing.
      for (const anchor of svg.querySelectorAll('a:not([data-drawio-id])')) {
        anchor.setAttribute('tabindex', '-1');
        anchor.setAttribute('aria-hidden', 'true');
      }
      const width = parseFloat(svg.getAttribute('width'));
      const height = parseFloat(svg.getAttribute('height'));
      if (!(width > 0 && height > 0)) throw new Error('The official SVG has invalid dimensions.');
      if (!svg.hasAttribute('viewBox')) svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
      const vertexCount = cells.filter(cell => cell.kind === 'vertex').length;
      const edgeCount = cells.filter(cell => cell.kind === 'edge').length;
      const audit = {renderer: 'draw.io', version: VERSION, sourceCellCount: sourceCells.size,
        renderedCellCount: seen.size, vertexCount, edgeCount,
        visualUnchanged: true, visualSignature: fingerprint(originalVisual),
        sourceXmlModified: false, linkCount: cells.filter(cell => cell.linked).length};
      svg.setAttribute('role', 'group');
      svg.setAttribute('aria-label', options.label || 'Original Validation.drawio semantic model');
      svg.setAttribute('data-renderer', 'draw.io ' + VERSION);
      svg.setAttribute('data-audit', JSON.stringify(audit));
      svg.classList.add('drawio-original');
      return {svg, width, height, cells, vertexCount, edgeCount, audit, rendererVersion: VERSION};
    } finally {
      if (window.ResizeSensor?.detach) ResizeSensor.detach(host);
      viewer?.graph?.destroy();
      host.remove();
    }
  }

  function mount(container, options = {}) {
    const result = render(options);
    container.replaceChildren(result.svg);
    const navigate = event => {
      const anchor = event.target.closest('a[data-drawio-id]');
      if (!anchor || !options.onNavigate || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      if (options.onNavigate({id: anchor.dataset.drawioId, url: anchor.getAttribute('href'), anchor, event}) === false) event.preventDefault();
    };
    result.svg.addEventListener('click', navigate);
    return {...result, destroy() { result.svg.removeEventListener('click', navigate); result.svg.remove(); }};
  }

  window.HeleShawDrawio = Object.freeze({render, mount, rendererVersion: VERSION});
})();
