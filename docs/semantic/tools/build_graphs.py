# SPDX-FileCopyrightText: 2026 Vasiliy Seibert
# SPDX-License-Identifier: MIT
"""Precompute offline SVG views from the shared Hele-Shaw semantic dataset."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from graph_layout import colors, gap_label, render_overview, render_workflow, wrapped

HERE = Path(__file__).resolve().parents[1]
SVG = 'http://www.w3.org/2000/svg'
ET.register_namespace('', SVG)


def legend(selected, entities):
    kinds = {}
    for identifier in selected:
        entity = entities[identifier]
        kinds[entity['kind']] = colors(entity)[0]
    return [{'label': kind, 'fill': fill} for kind, fill in sorted(kinds.items())]


def neighborhood(selected, edges, entities, indices):
    lines = ['digraph G { graph [rankdir=LR, bgcolor="transparent", pad="0.45", nodesep="0.48", ranksep="1.0", splines=polyline, outputorder=edgesfirst]; node [shape=box, style="rounded,filled", fontname="Arial", fontsize=16, margin="0.18,0.15", penwidth=1.5]; edge [fontname="Arial", fontsize=11, color="#657580", fontcolor="#46515a", arrowsize=0.65];']
    for identifier in sorted(selected):
        entity = entities[identifier]
        caption = entity.get('displayType') or entity['types'][0]
        label = '\n'.join(wrapped(entity.get('displayLabel') or entity['label']) + [caption])
        if gap_label(entity):
            label += '\n' + gap_label(entity)
        fill, border = colors(entity)
        lines.append(f'n{indices[identifier]} [id="entity-{indices[identifier]}", label={json.dumps(label, ensure_ascii=False)}, fillcolor="{fill}", color="{border}"];')
    for number, edge in enumerate(edges):
        proposed = edge.get('asserted') is False or 'propos' in edge.get('status', '').lower()
        label = edge.get('label') or edge.get('normalizedLabel') or 'related to'
        if proposed:
            label += ' · proposed'
        style = 'dashed' if proposed else 'solid'
        lines.append(f'n{indices[edge["source"]]} -> n{indices[edge["target"]]} [id="relation-{number}", label={json.dumps(label, ensure_ascii=False)}, style="{style}"];')
    lines.append('}')
    output = subprocess.check_output(['dot', '-Tsvg'], input='\n'.join(lines).encode())
    root = ET.fromstring(output)
    root.set('role', 'img')
    for element in root.iter():
        identifier = element.get('id', '')
        if identifier.startswith('relation-'):
            edge = edges[int(identifier.removeprefix('relation-'))]
            for key in ('source', 'target', 'predicate', 'id'):
                element.set('data-' + key, str(edge.get(key, '')))
        elif identifier.startswith('entity-'):
            element.set('data-entity', next(key for key in selected if indices[key] == int(identifier.removeprefix('entity-'))))
    return ET.tostring(root, encoding='unicode')


def build():
    model = json.loads((HERE / 'data/model.json').read_text())
    entities = {entity['id']: entity for entity in model['entities']}
    indices = {entity['id']: index for index, entity in enumerate(model['entities'])}
    graphs = {}
    for key, view in [('overview', model['overview'])] + [(workflow['graphKey'], workflow) for workflow in model['workflows']]:
        selected = view['entities']
        if not set(selected) <= entities.keys():
            raise ValueError(f'Unknown entity in {key}')
        svg = render_overview(view, entities, indices) if key == 'overview' else render_workflow(view, entities, indices)
        graphs[key] = {'svg': svg, 'count': len(selected), 'total': len(selected), 'legend': legend(selected, entities)}
    for identifier in entities:
        incident = [edge for edge in model['edges'] if identifier in (edge['source'], edge['target'])]
        neighbors = sorted({edge['target'] if edge['source'] == identifier else edge['source'] for edge in incident} - {identifier})
        selected = {identifier, *neighbors[:28]}
        chosen = [edge for edge in incident if edge['source'] in selected and edge['target'] in selected]
        graphs[identifier] = {'svg': neighborhood(selected, chosen, entities, indices), 'count': len(selected), 'total': len(neighbors) + 1, 'legend': legend(selected, entities)}
    (HERE / 'data/graphs.js').write_text('window.HELE_SHAW_GRAPHS = ' + json.dumps(graphs, ensure_ascii=False) + ';\n')
    print(f'Built {len(graphs)} offline diagrams ({len(model["workflows"])} workflows; neighborhoods capped at 28 neighbors)')


if __name__ == '__main__':
    build()
