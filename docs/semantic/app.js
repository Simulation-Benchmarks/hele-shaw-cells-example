// SPDX-FileCopyrightText: 2026 Vasiliy Seibert
// SPDX-License-Identifier: MIT
// Adapted from FAIR4SD semantic atlas.
(() => {
'use strict';
const $ = id => document.getElementById(id);
const m = window.HELE_SHAW, graphs = window.HELE_SHAW_GRAPHS;
if (!m || !graphs) {
  $('drawing').innerHTML = '<h1>The diagram could not load</h1><p>Reload the page to try again, or read the semantic model directly.</p><a href="model.ttl" target="_blank" rel="noopener noreferrer">Read RDF source ↗</a>';
  $('drawing').classList.add('load-error');
  document.querySelectorAll('.map-caption,.legend,.zoom').forEach(el => el.hidden = true);
  document.querySelectorAll('header nav a').forEach(link => {
    link.setAttribute('aria-disabled', 'true');
    link.addEventListener('click', event => event.preventDefault());
  });
  $('drawing').setAttribute('role', 'alert');
  $('status').textContent = 'Semantic diagram data is unavailable.';
  document.querySelectorAll('button,input').forEach(x => x.disabled = true);
  return;
}
const entities = new Map(m.entities.map(e => [e.id, e]));
const original = window.HELE_SHAW_DRAWIO;
const workflows = new Map(m.workflows.map(workflow => [workflow.slug, workflow]));
const siteTitle = m.meta.repository.replace('https://github.com/', '');
const names = {overview: 'Semantic Model', ...Object.fromEntries(m.workflows.map(w => [w.graphKey, w.title]))};
const canvas = $('canvas'), drawing = $('drawing'), tip = $('tip');
let key = 'overview', section = 'overview', context = '', documentView = false;
let scale = 1, x = 0, y = 0, w = 100, h = 100, drag = null, tipTimer, originalSvg;
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const sourceFor = e => e.navigation === 'explore' ? null : (e.launchUrl || e.previewUrl) ? {url: e.launchUrl || e.previewUrl, target: e.launchUrl ? '_self' : '_blank'} : e.sources?.[0];
const entityLink = (id, owner = context) => '#' + (section === 'workflows' ? 'workflows' : 'overview') + '/' + encodeURIComponent(id)
  + (section === 'workflows' && owner ? '?from=' + encodeURIComponent(owner) : '');
const legendMarkup = graph => (graph.legend || []).map(item =>
  `<span style="--swatch:${esc(item.fill)}">${esc(item.label)}</span>`).join('');

document.querySelector('.skip-link').addEventListener('click', event => {
  event.preventDefault();
  const target = document.querySelector(event.currentTarget.getAttribute('href'));
  target?.focus({preventScroll:true});
  if (documentView) target?.scrollIntoView({block:'start'});
});

function transform() { drawing.style.transform = `translate(${x}px,${y}px) scale(${scale})`; }
function fit() {
  if (documentView) return;
  const top = Math.max(65, document.querySelector('.map-caption').getBoundingClientRect().bottom - canvas.getBoundingClientRect().top + 20);
  const available = Math.max(80, canvas.clientHeight - top - 85);
  scale = Math.max(.015, Math.min((canvas.clientWidth - 40) / w, available / h, 1.4));
  x = (canvas.clientWidth - w * scale) / 2;
  y = top + (available - h * scale) / 2;
  transform();
}
function zoom(f, cx = canvas.clientWidth / 2, cy = canvas.clientHeight / 2) {
  if (documentView) return;
  const next = Math.max(.015, Math.min(4, scale * f));
  x = cx - (cx - x) * next / scale; y = cy - (cy - y) * next / scale;
  scale = next; transform(); hide();
}
window.mapAction = action => {
  if (action === 'clear') {
    $('search').value = ''; $('search').dispatchEvent(new Event('input')); $('search').focus(); return;
  }
  action === 'fit' ? fit() : zoom(action === 'in' ? 1.25 : .8);
};
function hide() { clearTimeout(tipTimer); tip.hidden = true; }
tip.addEventListener('mouseenter', () => clearTimeout(tipTimer));
tip.addEventListener('mouseleave', hide);
function show(e, node, event) {
  clearTimeout(tipTimer);
  const source = sourceFor(e);
  const hint = source ? e.sourceAction || 'open ' + (source.url.includes('github.com') ? 'GitHub source' : 'source') : 'explore connections';
  tip.innerHTML = `<strong>${esc(e.label)}</strong><small>${esc(e.types.join(' · '))} · ${esc(e.status || 'Extracted')}</small>
    <p>${esc(e.definition)}</p>${e.details ? `<ul>${e.details.map(d => `<li>${esc(d)}</li>`).join('')}</ul>` : ''}
    ${(e.unit || e.unitLabel) ? `<p>Unit: ${esc(e.unit || e.unitLabel)}</p>` : ''}${e.equation ? `<p><code>${esc(e.equation)}</code></p>` : ''}
    ${e.bindings?.length ? `<p><code>${esc(e.bindings[0].selector)}</code></p>` : ''}
    <div class="hint">Click to ${esc(hint)}${source ? (source.target === '_self' ? ' →' : ' ↗') : ''}</div>`;
  tip.hidden = false;
  const focusTarget = node.querySelector('foreignObject > div > div > div') || node;
  const r = focusTarget.getBoundingClientRect(), tx = event?.clientX ?? r.right, ty = event?.clientY ?? r.top;
  tip.style.left = Math.max(12, Math.min(innerWidth - tip.offsetWidth - 12, tx + 16)) + 'px';
  tip.style.top = Math.max(12, Math.min(innerHeight - tip.offsetHeight - 12, ty + 16)) + 'px';
  node.parentElement.setAttribute('aria-describedby', 'tip');
}

function showOriginal(link, node, event) {
  const entity = entities.get(link.entityId);
  const status = link.status || entity?.status || 'Original diagram';
  clearTimeout(tipTimer);
  tip.innerHTML = `<strong>${esc(link.label || link.originalLabel || 'Unlabelled relationship')}</strong>
    <small>${esc(status)}</small><p>${esc(link.reviewNote || entity?.definition || 'Original relationship from Validation.drawio. Open its mapping details for evidence and interpretation.')}</p>
    <div class="hint">${link.type === 'edge' ? 'Open relationship details →' : link.url.startsWith('#') ? 'Explore connections →' : 'Open linked source ↗'}</div>`;
  tip.hidden = false;
  const focusTarget = node.querySelector('foreignObject > div > div > div') || node;
  const r = focusTarget.getBoundingClientRect(), tx = event?.clientX ?? r.right, ty = event?.clientY ?? r.top;
  tip.style.left = Math.max(12, Math.min(innerWidth - tip.offsetWidth - 12, tx + 16)) + 'px';
  tip.style.top = Math.max(12, Math.min(innerHeight - tip.offsetHeight - 12, ty + 16)) + 'px';
  node.setAttribute('aria-describedby', 'tip');
}

function bindOriginal() {
  if (!original || !window.HeleShawDrawio) throw new Error('The original drawing renderer could not load.');
  if (!originalSvg) originalSvg = window.HeleShawDrawio.render(original).svg;
  drawing.replaceChildren(originalSvg.cloneNode(true));
  const svg = drawing.querySelector('svg');
  svg.setAttribute('role', 'group');
  svg.setAttribute('aria-label', 'Original Validation.drawio: 112 entities and 100 relationships');
  svg.querySelectorAll('a').forEach(anchor => {
    const cell = anchor.closest('[data-drawio-id]') || anchor.querySelector('[data-drawio-id]');
    const id = anchor.getAttribute('data-drawio-id') || cell?.getAttribute('data-drawio-id');
    const link = original.links[id];
    if (!link) return;
    anchor.setAttribute('tabindex', '0');
    anchor.addEventListener('mouseenter', ev => showOriginal(link, anchor, ev));
    anchor.addEventListener('mouseleave', () => { tipTimer = setTimeout(hide, 180); });
    anchor.addEventListener('focus', () => showOriginal(link, anchor));
    anchor.addEventListener('blur', hide);
  });
  return svg;
}

function renderRelationship(id) {
  const link = original?.links[id], page = $('relationship-page');
  if (!link || link.type !== 'edge') {
    page.innerHTML = '<h1 id="relationship-title" tabindex="-1">Relationship unavailable</h1><p>This diagram identifier was not found.</p><a href="#overview">Return to the original drawing →</a>';
    return;
  }
  const endpoint = diagramId => {
    const item = original.links[diagramId];
    return item ? `<a href="#overview/${encodeURIComponent(item.entityId)}">${esc(item.label || 'Unlabelled entity')}</a>` : esc(diagramId);
  };
  const mappedEndpoint = entityId => `<a href="#overview/${encodeURIComponent(entityId)}">${esc(entities.get(entityId)?.label || entityId)}</a>`;
  const predicateUrl = link.predicate.startsWith(m.meta.namespace + 'vocabulary.ttl#')
    ? 'vocabulary.ttl#' + link.predicate.split('#').pop() : link.predicate;
  page.innerHTML = `<a class="back-contents" href="#overview">← Original semantic model</a>
    <div class="workflow-intro"><p class="eyebrow">Original relationship</p><h1 id="relationship-title" tabindex="-1">${esc(link.originalLabel || link.label || 'Unlabelled arrow')}</h1>
    <p>${endpoint(link.sourceDiagramId)} → ${endpoint(link.targetDiagramId)}</p></div>
    <p class="relationship-status">${esc(link.status)}${link.asserted === false ? ' · interpretation requires review' : ''}</p>
    <p>The arrow above follows the source drawing exactly. Its mapping into the semantic dataset is recorded below.</p>
    ${link.reviewNote ? `<p class="relationship-note">${esc(link.reviewNote)}</p>` : ''}
    ${link.directionNormalized ? '<p class="relationship-note">The semantic dataset normalizes this relationship’s direction. The drawing keeps the original direction.</p>' : ''}
    <dl><dt>Original label</dt><dd>${esc(link.originalLabel || '(no label in the drawing)')}</dd>
    <dt>Mapped direction${link.asserted === false ? ' (proposed)' : ''}</dt><dd>${mappedEndpoint(link.mappedSource)} → ${mappedEndpoint(link.mappedTarget)}</dd>
    <dt>Mapped predicate</dt><dd><a href="${esc(predicateUrl)}" target="_blank" rel="noopener noreferrer">${esc(link.predicate)}</a></dd>
    <dt>Diagram identifier</dt><dd><code>${esc(id)}</code></dd></dl>
    <div class="workflow-actions"><a href="source/Validation.drawio" download>Download original drawing ↓</a><a href="source/diagram-crosswalk.json" target="_blank" rel="noopener noreferrer">Read mapping record ↗</a></div>`;
  document.title = (link.originalLabel || 'Unlabelled relationship') + ' — ' + siteTitle;
  window.scrollTo(0, 0); $('relationship-title').focus({preventScroll:true});
  $('status').textContent = 'Showing original relationship and mapping status';
}

// Shared by the full canvas and inline diagrams. Graph markup is generated
// locally; the builders and tooltip renderer escape entity text.
function bindGraph(container, graph, label, owner = '', prefix = 'canvas') {
  container.innerHTML = graph.svg;
  const svg = container.querySelector('svg');
  svg.setAttribute('aria-label', label);
  // Keep interactive SVG links exposed to assistive technology.
  svg.setAttribute('role', 'group');
  svg.querySelectorAll('title').forEach(t => t.remove());
  svg.querySelectorAll('.node').forEach(node => {
    const e = m.entities[Number(node.id.replace('entity-', ''))];
    if (!e) return;
    const source = sourceFor(e), anchor = document.createElementNS('http://www.w3.org/2000/svg', 'a');
    anchor.setAttribute('href', source?.url || (owner ? '#workflows/' + encodeURIComponent(e.id) + '?from=' + owner : entityLink(e.id)));
    if (source) { anchor.setAttribute('target', source.target || '_blank'); anchor.setAttribute('rel', 'noopener noreferrer'); }
    anchor.setAttribute('aria-label', e.label + ' — ' + (source ? e.sourceAction || 'open source' : 'explore connections'));
    anchor.setAttribute('tabindex', '0'); anchor.setAttribute('data-entity', e.id);
    node.parentNode.insertBefore(anchor, node); anchor.appendChild(node);
    node.setAttribute('tabindex', '-1');
    anchor.addEventListener('mouseenter', ev => show(e, node, ev));
    anchor.addEventListener('mouseleave', () => { tipTimer = setTimeout(hide, 180); });
    anchor.addEventListener('focus', () => show(e, node)); anchor.addEventListener('blur', hide);
    if (source) { const text = node.querySelector('text'); if (text) text.textContent += source.target === '_self' ? ' →' : ' ↗'; }
  });
  // Repeated entities and Graphviz markers need unique IDs in one document.
  const ids = new Map([...svg.querySelectorAll('[id]')].map(el => [el.id, prefix + '-' + el.id]));
  svg.querySelectorAll('*').forEach(el => {
    for (const attr of [...el.attributes]) if (attr.value.includes('url(#')) {
      el.setAttribute(attr.name, attr.value.replace(/url\(#([^)]+)\)/g, (_, id) => `url(#${ids.get(id) || id})`));
    }
    if (el.id) el.id = ids.get(el.id);
  });
  return svg;
}

function buildCatalog() {
  $('workflow-page').innerHTML = `<div id="workflows" class="workflow-intro"><p class="eyebrow">Repository examples</p>
    <h1 id="workflows-title" tabindex="-1">Workflows</h1>
    <p>Follow artifacts through the repository, from model inputs to results and analysis.</p></div>
    <nav class="workflow-contents" aria-label="Workflow contents"><h2>Contents</h2><ol>
    ${m.workflows.map(w => `<li><a href="#workflow-${esc(w.slug)}">${esc(w.title)}</a><p>${esc(w.summary)}</p></li>`).join('')}
    </ol></nav><div class="workflow-sections">${m.workflows.map((workflow, index) => `
      <article class="workflow-section" id="workflow-${esc(workflow.slug)}" aria-labelledby="heading-${esc(workflow.slug)}">
        <div class="workflow-heading"><div><p class="eyebrow">Workflow ${index + 1}</p>
        <h2 id="heading-${esc(workflow.slug)}" tabindex="-1">${esc(workflow.title)}</h2></div><a class="back-contents" href="#workflows">↑ Contents</a></div>
        <p class="workflow-summary">${esc(workflow.summary)}</p><p class="workflow-evidence">${esc(workflow.caveat)}</p>
        <div class="workflow-actions"><a class="diagram-link" href="#workflows/${workflow.graphKey}">Explore diagram</a>
        ${(workflow.actions || []).map(action => `<a href="${esc(action.url)}" target="${action.sameTab ? '_self' : '_blank'}" rel="noopener noreferrer">${esc(action.label)} ${action.sameTab ? '→' : '↗'}</a>`).join('')}</div>
        <div class="inline-diagram" tabindex="0" role="region" aria-label="${esc(workflow.title)} diagram; scroll horizontally if needed"><div class="semantic-graph" data-workflow="${esc(workflow.slug)}"></div></div>
        <div class="inline-legend" aria-label="Entity colours">${legendMarkup(graphs[workflow.graphKey])}</div>
        ${workflow.note ? `<div class="workflow-notes"><p>${esc(workflow.note)}</p></div>` : ''}
      </article>`).join('')}</div>`;
  $('workflow-page').querySelectorAll('[data-workflow]').forEach(container => {
    const workflow = workflows.get(container.dataset.workflow);
    bindGraph(container, graphs[workflow.graphKey], workflow.title, workflow.slug, workflow.slug);
  });
}

function buildUseCases() {
  $('use-cases-page').innerHTML = `<div class="workflow-intro"><p class="eyebrow">Services in practice</p>
    <h1 id="use-cases-title" tabindex="-1">NFDI4Ing Use Cases</h1>
    <p>Follow the benchmark through platform, notebook and research-object services. Each entry states the available evidence.</p></div>
    <div class="service-list">${(m.services || []).map(service => `
      <section class="service-entry" aria-labelledby="service-${esc(service.id)}">
        <div class="service-heading"><p class="eyebrow">Service</p>
          ${service.logos?.length ? `<div class="service-logos">${service.logos.map(logo => `<img src="${esc(logo.src)}" alt="${esc(logo.alt)}" width="${logo.width}" height="${logo.height}">`).join('')}</div>` : ''}
          <h2 id="service-${esc(service.id)}">${esc(service.name)}</h2>
          ${service.status ? `<p class="service-status">${esc(service.status)}</p>` : ""}
          ${service.summary ? `<p class="service-summary">${esc(service.summary)}</p>` : ""}
          <a href="${esc(service.url)}" target="_blank" rel="noopener noreferrer">Visit service ↗</a></div>
        <div class="service-use-cases">${service.workflowSlugs.map(slug => {
          const workflow = workflows.get(slug);
          return `<article class="service-use-case"><p class="eyebrow">Use case</p>
            <p class="use-case-statement"><a href="#workflow-${esc(slug)}">${esc(workflow.title)}</a></p>
            <div class="workflow-actions"><a class="diagram-link" href="#workflow-${esc(slug)}">View workflow →</a></div>
          </article>`;
        }).join('')}</div>
      </section>`).join('') || '<p>No service use cases are listed yet.</p>'}</div>`;
}

function render() {
  const [rawPath, query = ''] = location.hash.slice(1).split('?');
  let route; try { route = decodeURIComponent(rawPath); } catch { route = 'overview'; }
  const anchor = route.startsWith('workflow-') ? route.slice('workflow-'.length) : '';
  const useCasesView = route === 'nfdi4ing';
  const relationshipView = route.startsWith('relationship/');
  const workflowView = route === 'workflows' || workflows.has(anchor);
  documentView = useCasesView || workflowView || relationshipView;
  section = useCasesView ? 'nfdi4ing' : workflowView || route.startsWith('workflows/') ? 'workflows' : 'overview';
  context = workflows.has(anchor) ? anchor : new URLSearchParams(query).get('from') || '';
  if (!workflows.has(context)) context = '';
  key = route.replace(/^(overview|workflows)\//, '') || 'overview';
  if (!documentView && !graphs[key]) { key = 'overview'; section = 'overview'; context = ''; }
  const workflow = m.workflows.find(w => w.graphKey === key);
  if (workflow) context = workflow.slug;
  document.documentElement.classList.toggle('document-view', documentView);
  document.body.dataset.view = relationshipView ? 'relationship' : documentView ? section : 'diagram';
  $('workflow-page').hidden = !workflowView;
  $('use-cases-page').hidden = !useCasesView; canvas.hidden = documentView;
  $('relationship-page').hidden = !relationshipView;
  document.querySelectorAll('.map-caption,.legend,.zoom').forEach(el => el.hidden = documentView);
  document.querySelectorAll('header nav a').forEach(a => {
    if (a.hash === '#' + section) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
  });
  $('results').hidden = true; $('search').setAttribute('aria-expanded', 'false'); hide();
  const skip = document.querySelector('.skip-link');
  skip.href = relationshipView ? '#relationship-title' : useCasesView ? '#use-cases-title' : workflowView ? (anchor ? '#heading-' + anchor : '#workflows-title') : '#drawing';
  skip.textContent = documentView ? 'Skip to page content' : 'Skip to semantic diagram';
  if (relationshipView) { renderRelationship(route.slice('relationship/'.length)); return; }
  if (useCasesView) {
    document.title = 'NFDI4Ing Use Cases — ' + siteTitle;
    window.scrollTo(0, 0); $('use-cases-title').focus({preventScroll: true});
    $('status').textContent = 'Showing NFDI4Ing Use Cases';
    return;
  }
  if (documentView) {
    document.title = (anchor ? workflows.get(anchor).title : 'Workflows') + ' — ' + siteTitle;
    const heading = anchor ? $('heading-' + anchor) : $('workflows-title');
    const target = anchor ? $('workflow-' + anchor) : $('workflow-page');
    target.scrollIntoView({block: 'start'}); heading.focus({preventScroll: true});
    $('status').textContent = anchor ? 'Showing ' + workflows.get(anchor).title : `Workflows, ${m.workflows.length} examples`;
    return;
  }
  window.scrollTo(0, 0);
  const graph = graphs[key], title = names[key] || entities.get(key)?.label || 'Semantic map';
  drawing.classList.toggle('semantic-graph', key !== 'overview');
  drawing.classList.toggle('original-drawio', key === 'overview');
  drawing.classList.remove('load-error');
  let svg;
  try { svg = key === 'overview' ? bindOriginal() : bindGraph(drawing, graph, title, context); }
  catch (error) {
    drawing.style.transform = ''; drawing.classList.add('load-error');
    drawing.innerHTML = '<h1>The original drawing could not load</h1><p>Reload to try again, or download the original file.</p><a href="source/Validation.drawio" download>Download Validation.drawio ↓</a>';
    document.querySelectorAll('.map-caption,.legend,.zoom').forEach(el => el.hidden = true);
    $('status').textContent = error.message; return;
  }
  w = svg.viewBox.baseVal.width; h = svg.viewBox.baseVal.height;
  svg.setAttribute('width', w); svg.setAttribute('height', h);
  document.querySelector('.legend').innerHTML = legendMarkup(graph);
  document.querySelector('.legend').hidden = key === 'overview';
  $('map-title').textContent = title;
  $('map-count').textContent = key === 'overview' ? '112 entities · 100 relationships · original layout' : `${graph.count} entities` + (graph.total > graph.count ? ` · ${graph.total - graph.count} more connections in RDF` : '');
  const description = workflow?.summary || (key === 'overview' ? 'Validation.drawio, unchanged. Select an entity for its source or an arrow for mapping details.' : entities.get(key)?.definition) || '';
  $('map-description').hidden = !description; $('map-description').textContent = description;
  $('back-to-workflows').hidden = section !== 'workflows';
  $('back-to-workflows').href = context ? '#workflow-' + context : '#workflows';
  $('back-to-model').hidden = section !== 'overview' || key === 'overview';
  $('drawio-actions').hidden = key !== 'overview';
  document.title = title + ' — ' + siteTitle; fit();
  $('status').textContent = key === 'overview' ? 'Showing original Validation.drawio, all 112 entities and 100 relationships' : `Showing ${title}, ${graph.count} entities`;
  if (graph.total > graph.count) $('status').textContent += `; ${graph.total - graph.count} connections omitted from this view, retained in RDF.`;
}

$('search').addEventListener('input', e => {
  if (e.isComposing) return;
  const q = $('search').value.trim().toLowerCase(), results = $('results');
  $('clear-search').hidden = !$('search').value; results.hidden = !q; $('search').setAttribute('aria-expanded', String(Boolean(q))); if (!q) return;
  const normalize = text => text.toLowerCase().replace(/[_.-]+/g, ' ');
  const found = m.entities.filter(e => normalize(e.label + ' ' + (e.path || '') + ' ' + e.kind).includes(normalize(q)))
    .sort((a, b) => Number(a.id.startsWith('diagram-cell/')) - Number(b.id.startsWith('diagram-cell/'))).slice(0, 18);
  results.innerHTML = found.length ? found.map(e => `<a href="${entityLink(e.id)}">${esc(e.label)}<small>${esc(e.kind)} · ${esc(e.status)} · explore connections</small></a>`).join('') : '<p>No matching entities. Try “flow rate”, “finger” or “parameters”.</p>';
});
$('search').addEventListener('compositionend', () => $('search').dispatchEvent(new Event('input')));
$('search').addEventListener('keydown', e => {
  if (e.isComposing) return;
  if (e.key === 'ArrowDown') { $('results').querySelector('a')?.focus(); e.preventDefault(); }
  if (e.key === 'Enter') $('results').querySelector('a')?.click();
});
$('results').addEventListener('keydown', e => {
  const links = [...$('results').querySelectorAll('a')], index = links.indexOf(document.activeElement);
  if (e.key === 'ArrowDown') { e.preventDefault(); links[Math.min(index + 1, links.length - 1)]?.focus(); }
  if (e.key === 'ArrowUp') { e.preventDefault(); if (index <= 0) $('search').focus(); else links[index - 1].focus(); }
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') { e.preventDefault(); hide(); $('results').hidden = true; $('search').setAttribute('aria-expanded', 'false'); }
  if (e.isComposing || e.target.matches('input') || e.target.closest('#results') || documentView) return;
  if (['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)) {
    e.preventDefault(); x += e.key === 'ArrowLeft' ? 80 : e.key === 'ArrowRight' ? -80 : 0;
    y += e.key === 'ArrowUp' ? 80 : e.key === 'ArrowDown' ? -80 : 0; transform(); hide();
  }
  if (e.key === '+' || e.key === '=') zoom(1.25); if (e.key === '-') zoom(.8);
});
canvas.addEventListener('wheel', e => {
  e.preventDefault(); const r = canvas.getBoundingClientRect();
  zoom(Math.exp(-e.deltaY * .0015), e.clientX - r.left, e.clientY - r.top);
}, {passive: false});
canvas.addEventListener('pointerdown', e => {
  if (e.target.closest('a')) return;
  drag = {px:e.clientX, py:e.clientY, x, y}; canvas.setPointerCapture(e.pointerId);
  canvas.classList.add('dragging'); hide();
});
canvas.addEventListener('pointermove', e => {
  if (!drag) return; x = drag.x + e.clientX - drag.px; y = drag.y + e.clientY - drag.py; transform();
});
function end() { drag = null; canvas.classList.remove('dragging'); }
canvas.addEventListener('pointerup', end); canvas.addEventListener('pointercancel', end);
document.addEventListener('scroll', e => { if (e.target !== tip) hide(); }, true);
addEventListener('hashchange', render); addEventListener('resize', fit);
buildCatalog(); buildUseCases(); render();
})();
