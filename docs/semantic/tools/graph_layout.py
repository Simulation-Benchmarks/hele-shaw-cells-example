# SPDX-FileCopyrightText: 2026 Vasiliy Seibert
# SPDX-License-Identifier: MIT
"""Diagram primitives adapted from FAIR4SD's MIT semantic atlas viewer.

Only presentation is reused. Labels, relationships and evidence come from the
Hele-Shaw semantic projection; no Kaibab model content is imported.
"""
from html import escape
import textwrap

PALETTE = {
    'Model': ('#bfdeeb', '#3f7f9e'),
    'Literature': ('#eee5f4', '#9476ac'),
    'Concept': ('#f9ddd7', '#bc6354'),
    'Quantity': ('#ffffff', '#718894'),
    'Variable': ('#ffffff', '#718894'),
    'Numerical variable': ('#ffffff', '#718894'),
    'File': ('#dce9ff', '#7698c6'),
    'Dataset': ('#dce9ff', '#7698c6'),
    'Artifact': ('#dce9ff', '#7698c6'),
    'Script': ('#dce9ff', '#7698c6'),
    'Notebook': ('#eee5f4', '#9476ac'),
    'Processing step': ('#d8ead0', '#80a865'),
    'ProcessingStep': ('#d8ead0', '#80a865'),
    'Process': ('#d8ead0', '#80a865'),
    'Run': ('#d8ead0', '#80a865'),
    'Method': ('#ffe8cc', '#cd963f'),
    'Tool': ('#fff2ce', '#c9ac54'),
    'Software': ('#fff2ce', '#c9ac54'),
    'Material': ('#f9ddd7', '#bc6354'),
    'Formula': ('#d6e7ed', '#6993a6'),
    'Task': ('#f9ddd7', '#bc6354'),
    'Variable set': ('#ffffff', '#718894'),
    'Repository': ('#dce9ff', '#7698c6'),
    'Note': ('#fcf2e7', '#cd963f'),
    'Vocabulary': ('#eee5f4', '#9476ac'),
    'Configuration': ('#ffffbd', '#aaa354'),
    'Assignment': ('#e4d7ec', '#9c7ab1'),
    'Binding': ('#e4d7ec', '#9c7ab1'),
    'Field': ('#e4d7ec', '#9c7ab1'),
    'Unit': ('#c6d7e0', '#648295'),
    'Validation': ('#d8ead0', '#80a865'),
}


def colors(entity):
    kind = entity.get('kind', '')
    if kind in PALETTE:
        return PALETTE[kind]
    for type_name in entity.get('types', []):
        tail = type_name.rsplit(':', 1)[-1]
        if tail in PALETTE:
            return PALETTE[tail]
    return '#ffffff', '#718894'


def gap_label(entity):
    status = entity.get('status', '').lower()
    if 'concept' in status:
        return 'Conceptual · evidence not supplied'
    if 'propos' in status:
        return 'Proposed · mapping needs review'
    if 'unverified' in status or 'missing' in status:
        return 'Unverified · evidence incomplete'
    return ''


def wrapped(text, width=29):
    return [line for paragraph in str(text).split('\n')
            for line in textwrap.wrap(paragraph, width, break_long_words=False,
                                      break_on_hyphens=False)] or ['']


def svg_start(width, height):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img">',
            '<defs><marker id="flow-arrow" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L8,4 L0,8 Z" fill="#657580"/></marker></defs>']


def text_lines(parts, lines, x, y, *, size=16, color='#182f3a', anchor='middle', weight='400', spacing=21, halo=False):
    for number, line in enumerate(lines):
        halo_attr = ' stroke="white" stroke-width="5" paint-order="stroke" stroke-linejoin="round"' if halo else ''
        parts.append(f'<text x="{x}" y="{y + number * spacing}" text-anchor="{anchor}" font-family="Arial, Helvetica, sans-serif" font-size="{size}" font-weight="{weight}" fill="{color}"{halo_attr}>{escape(str(line))}</text>')


def draw_node(parts, entity, index, position):
    x, y, width, height = position
    fill, border = colors(entity)
    gap = gap_label(entity)
    lines = wrapped(entity.get('displayLabel') or entity['label'])
    if len(lines) > 3:
        lines = [*lines[:2], lines[2].rstrip(' .') + '…']
    caption = entity.get('displayType') or (entity.get('types') or [entity.get('kind', '')])[0]
    caption_lines = wrapped(caption, 40)[:2]
    parts.append(f'<g class="node" id="entity-{index}" data-entity="{escape(entity["id"], quote=True)}"><rect x="{x}" y="{y}" width="{width}" height="{height}" rx="10" fill="{fill}" stroke="{border}" stroke-width="1.7"/>')
    title_y = y + ((height - (52 if gap else 36)) - (len(lines) - 1) * 21) / 2 + 6
    text_lines(parts, lines, x + width / 2, title_y, size=17, spacing=21)
    caption_y = y + height - (35 if gap else 16) - 13 * (len(caption_lines) - 1)
    text_lines(parts, caption_lines, x + width / 2, caption_y, size=11, color='#546872', spacing=13)
    if gap:
        text_lines(parts, [gap], x + width / 2, y + height - 13, size=10.5, color='#8b4c28')
    parts.append('</g>')


def draw_edges(parts, edges, positions, overrides=None):
    """Route only asserted/proposed data edges, preserving their direction."""
    for number, edge in enumerate(edges):
        if edge['source'] not in positions or edge['target'] not in positions:
            raise ValueError(f'Visible edge has an absent endpoint: {edge}')
        sx, sy, sw, sh = positions[edge['source']]
        tx, ty, tw, th = positions[edge['target']]
        scx, scy, tcx, tcy = sx + sw / 2, sy + sh / 2, tx + tw / 2, ty + th / 2
        lane = (number % 5 - 2) * 7
        label_width = 12
        override = (overrides or {}).get((edge['source'], edge['target']))
        if override:
            points, (lx, ly), label_width = override
            anchor = 'middle'
        elif abs(sx - tx) < 2 and abs(sy - ty) > 330:
            outside = sx + sw + 23 + abs(lane)
            points = [(sx + sw, scy), (outside, scy), (outside, tcy), (tx + tw, tcy)]
            lx, ly = outside, (scy + tcy) / 2 - 8
            anchor = 'middle'
        elif abs(sx - tx) < 2:
            # A same-column relation uses the vertical gap when adjacent.
            if sy < ty:
                points = [(scx, sy + sh), (tcx, ty)]
                lx, ly = scx + 16, (sy + sh + ty) / 2 - 5
            else:
                points = [(scx, sy), (tcx, ty + th)]
                lx, ly = scx + 16, (sy + ty + th) / 2 - 5
            anchor = 'start'
            label_width = 25
        elif abs(sx - tx) > 400:
            # Skip intermediate columns through a clear inter-row channel.
            forward = tx > sx
            start = (sx + sw, scy) if forward else (sx, scy)
            end = (tx, tcy) if forward else (tx + tw, tcy)
            gutter_start = start[0] + (20 if forward else -20)
            gutter_end = end[0] + (-20 if forward else 20)
            channel = (min(sy, ty) + sh + 20 + (number % 3) * 18) if abs(sy - ty) > 18 else min(sy, ty) - 26 - abs(lane)
            points = [start, (gutter_start, scy), (gutter_start, channel),
                      (gutter_end, channel), (gutter_end, tcy), end]
            lx, ly = (gutter_start + gutter_end) / 2, channel - 12
            anchor = 'middle'
            label_width = 26
        elif abs(scy - tcy) < 18:
            start = (sx + sw, scy) if tx > sx else (sx, scy)
            end = (tx, tcy) if tx > sx else (tx + tw, tcy)
            points = [start, end]
            lx, ly = (start[0] + end[0]) / 2, scy - 17
            anchor = 'middle'
        else:
            start = (sx + sw, scy) if tx > sx else (sx, scy)
            end = (tx, tcy) if tx > sx else (tx + tw, tcy)
            middle = (start[0] + end[0]) / 2 + lane
            points = [start, (middle, scy), (middle, tcy), end]
            lx, ly = middle, (scy + tcy) / 2 - 8
            anchor = 'middle'
        path = 'M' + ' L'.join(f'{x},{y}' for x, y in points)
        attrs = ' '.join(f'data-{key}="{escape(str(edge.get(key, "")), quote=True)}"' for key in ('source', 'target', 'predicate', 'id'))
        proposed = edge.get('asserted') is False or 'propos' in edge.get('status', '').lower()
        dash = ' stroke-dasharray="6 4"' if proposed else ''
        parts.append(f'<g class="edge" {attrs}><path d="{path}" fill="none" stroke="#657580" stroke-width="1.4"{dash} marker-end="url(#flow-arrow)"/>')
        label = edge.get('label') or edge.get('normalizedLabel') or 'related to'
        if proposed:
            label += '\nproposed'
        text_lines(parts, wrapped(label, label_width), lx, ly, size=11, color='#46515a', anchor=anchor, spacing=14, halo=True)
        parts.append('</g>')


def render_workflow(workflow, entities, indices):
    stages = workflow['stages']
    if len(stages) != 5:
        raise ValueError('The reference workflow design requires five stages')
    columns = [stage['entities'] for stage in stages]
    flattened = [identifier for column in columns for identifier in column]
    if len(flattened) != len(set(flattened)) or set(flattened) != set(workflow['entities']):
        raise ValueError(f'Every workflow node must belong to one stage: {workflow["slug"]}')
    positions = {}
    for column, identifiers in enumerate(columns):
        for row, identifier in enumerate(identifiers):
            positions[identifier] = (24 + column * 350, 185 + row * 190, 270, 130)
    height = 245 + max(map(len, columns)) * 190
    parts = svg_start(1750, height)
    for index, stage in enumerate(stages):
        x = 24 + index * 350
        text_lines(parts, wrapped(f'{index + 1} · {stage.get("title") or stage.get("label")}', 29), x, 31, size=17, anchor='start', weight='700')
        parts.append(f'<path d="M{x},76 h270" stroke="#d6e0e3"/>')
        text_lines(parts, wrapped(stage.get('summary', ''), 38)[:3], x, 99, size=12, color='#546872', anchor='start', spacing=16)
    routes = {}
    if workflow['slug'] == 'inspect-results':
        routes['step/visualisation', 'software/python-postprocessing'] = (
            [(1074, 250), (1054, 250), (1054, 353), (664, 353), (664, 440), (644, 440)],
            (745, 340), 25)
    draw_edges(parts, workflow['edges'], positions, routes)
    for identifier, position in positions.items():
        draw_node(parts, entities[identifier], indices[identifier], position)
    text_lines(parts, ['Dashed arrows are proposed relationships; conceptual and proposed nodes identify missing evidence.'], 24, height - 20, size=12, color='#546872', anchor='start')
    parts.append('</svg>')
    return ''.join(parts)


def render_overview(overview, entities, indices):
    groups = {group['id']: group for group in overview['groups']}
    positions = {}
    for row, group_id in enumerate(('model', 'experiment', 'simulation')):
        identifiers = groups[group_id]['entities']
        offset = 0 if group_id != 'experiment' else 1
        for column, identifier in enumerate(identifiers):
            positions[identifier] = (24 + (column + offset) * 325, 92 + row * 280, 255, 130)
    for row, identifier in enumerate(groups['validation']['entities']):
        positions[identifier] = (1730, 420 + row * 245, 265, 130)
    for column, identifier in enumerate(groups['imaging']['entities']):
        positions[identifier] = (674 + column * 325, 932, 255, 130)
    if set(positions) != set(overview['entities']):
        raise ValueError('Overview groups must contain exactly the visible overview nodes')
    parts = svg_start(2030, 1170)
    headings = []
    for row, group_id in enumerate(('model', 'experiment', 'simulation')):
        text_lines(headings, [groups[group_id]['title']], 24, 48 + row * 280, size=18, anchor='start', weight='700', halo=True)
        parts.append(f'<path d="M24,{61 + row * 280} h1555" stroke="#d6e0e3"/>')
    text_lines(parts, wrapped(groups['validation']['title'], 27), 1730, 365, size=18, anchor='start', weight='700')
    text_lines(headings, [groups['imaging']['title']], 24, 888, size=18, anchor='start', weight='700', halo=True)
    parts.append('<path d="M24,901 h1555" stroke="#d6e0e3"/>')
    routes = {}
    for number in (1, 2, 3):
        identifier = f'configuration/{number}'
        tx, ty, tw, th = positions[identifier]
        start_x, channel = 75 + number * 35, 235 + number * 25
        routes['step/preparation', identifier] = (
            [(start_x, 652), (start_x, channel), (tx + tw / 2, channel), (tx + tw / 2, ty + th)],
            ((start_x + tx + tw / 2) / 2, channel - 10), 25)
    routes['step/simulation', 'model'] = (
        [(349, 717), (294, 717), (294, 157), (279, 157)], (294, 557), 14)
    draw_edges(parts, overview['edges'], positions, routes)
    parts.extend(headings)
    for identifier, position in positions.items():
        draw_node(parts, entities[identifier], indices[identifier], position)
    text_lines(parts, ['Aligned with Validation.drawio · conceptual experiments and proposed validation remain visible evidence gaps.'], 24, 1140, size=13, color='#546872', anchor='start')
    parts.append('</svg>')
    return ''.join(parts)
