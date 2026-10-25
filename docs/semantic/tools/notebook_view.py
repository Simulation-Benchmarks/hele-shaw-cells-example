#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Vasiliy Seibert
# SPDX-License-Identifier: MIT
"""Render saved Hele-Shaw notebook evidence without starting a kernel.

Adapted from FAIR4SD's MIT notebook_view.py. Build requirements: nbformat,
nbconvert, beautifulsoup4 and latex2mathml==3.81.0. Math is converted to native
MathML at build time; the published view requires no scripts or remote assets.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import struct
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, NavigableString
import nbformat
from nbconvert import HTMLExporter
from nbconvert.filters import strip_ansi
from latex2mathml.converter import convert as latex_to_mathml

SITE = Path(__file__).resolve().parents[1]
REPO = SITE.parents[1]
SOURCE = REPO / 'notebooks/Simulation_Walkthrough.ipynb'
VIEW = SITE / 'notebooks/Simulation_Walkthrough.html'
MANIFEST = SITE / 'data/notebook-manifest.json'
REVISION = '8ec1b34f0a8fdbc103f35f88cba20e12b465800b'
REPOSITORY = 'https://github.com/Simulation-Benchmarks/hele-shaw-cells-example'
GIT = f'{REPOSITORY}/blob/{REVISION}/'

# Original cell indices, not execution counts: one figure cell was rerun.
SECTIONS = [
    (0, 'setup', 'Set up the walkthrough'),
    (2, 'build-image', 'Build the OpenFOAM image'),
    (4, 'mathematical-model', 'Read the mathematical model'),
    (5, 'governing-equations', 'Governing equations'),
    (6, 'gap-averaged-model', 'Gap-averaged model'),
    (7, 'initial-boundary-conditions', 'Initial and boundary conditions'),
    (8, 'dimensionless-numbers', 'Dimensionless numbers'),
    (10, 'reference-result', 'Reference simulation image'),
    (11, 'solver-numerics', 'Solver numerics'),
    (13, 'parameter-sweep', 'Inspect the three configurations'),
    (16, 'run-simulation', 'Follow the saved simulation run'),
    (22, 'inspect-results', 'Inspect the saved results'),
    (24, 'regression-checks', 'Read the saved regression checks'),
    (25, 'cartesian-figures', 'Inspect the Cartesian figures'),
    (27, 'alpha-field-inspection', 'Inspect the alpha field'),
    (29, 'finger-metrics', 'Inspect finger counts and radius'),
    (31, 'compare-reference', 'Compare with the reference'),
    (32, 'ro-crate-inspection', 'Inspect the local RO-Crate'),
    (33, 'next-steps', 'Further repository documentation'),
]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def cell_text(value) -> str:
    return ''.join(value) if isinstance(value, list) else value


def source_manifest(notebook) -> dict:
    cells, images = [], []
    for index, cell in enumerate(notebook.cells):
        outputs = []
        for output_index, output in enumerate(cell.get('outputs', [])):
            entry = {'index': output_index, 'type': output.output_type,
                     'sha256': digest(canonical(output))}
            if 'data' in output:
                entry['mimeTypes'] = sorted(output.data)
                if 'image/png' in output.data:
                    raw = base64.b64decode(cell_text(output.data['image/png']))
                    image = {'cellIndex': index, 'outputIndex': output_index,
                             'sha256': digest(raw), 'bytes': len(raw),
                             'width': struct.unpack('>I', raw[16:20])[0],
                             'height': struct.unpack('>I', raw[20:24])[0]}
                    images.append(image)
                    entry['imageSha256'] = image['sha256']
            outputs.append(entry)
        cells.append({'index': index, 'type': cell.cell_type,
                      'sourceSha256': digest(cell.source.encode()),
                      'executionCount': cell.get('execution_count'), 'outputs': outputs})
    code = [c for c in cells if c['type'] == 'code']
    return {
        'source': str(SOURCE.relative_to(REPO)), 'sourceRevision': REVISION,
        'sourceSha256': digest(SOURCE.read_bytes()),
        'view': str(VIEW.relative_to(SITE)),
        'executionPolicy': 'Render saved outputs only; no cells executed by this build.',
        'cellCount': len(cells), 'codeCellCount': len(code),
        'executedCodeCellCount': sum(c['executionCount'] is not None for c in code),
        'outputCount': sum(len(c['outputs']) for c in cells),
        'savedImageCount': len(images), 'cells': cells, 'images': images,
        'sections': [{'cellIndex': index, 'anchor': anchor, 'title': title,
                      'previewUrl': f'notebooks/Simulation_Walkthrough.html#{anchor}'}
                     for index, anchor, title in SECTIONS],
    }


MATH = re.compile(r'\$\$(.+?)\$\$|(?<!\\)\$([^$\n]+?)\$', re.DOTALL)


def render_math(soup):
    equations = []
    for region in soup.select('.text_cell_render'):
        for node in list(region.find_all(string=True)):
            if node.parent.name in {'code', 'pre', 'script', 'style'}:
                continue
            text = str(node)
            if not MATH.search(text):
                continue
            cursor = 0
            for match in MATH.finditer(text):
                node.insert_before(NavigableString(text[cursor:match.start()]))
                expression = match.group(1) or match.group(2)
                display = 'block' if match.group(1) is not None else 'inline'
                math = BeautifulSoup(latex_to_mathml(expression, display=display), 'html.parser').math
                math['aria-label'] = expression
                math['data-tex'] = expression
                node.insert_before(math)
                equations.append({'tex': expression, 'display': display})
                cursor = match.end()
            node.insert_before(NavigableString(text[cursor:]))
            node.extract()
    return equations


def image_description(source_index, image_index):
    if source_index == 26:
        return f'Saved configuration {image_index + 1}: Cartesian alpha field at five simulation times.'
    if source_index == 30:
        config = image_index // 2 + 1
        return (f'Saved configuration {config}: number of fingers over simulation time.'
                if image_index % 2 == 0 else
                f'Saved configuration {config}: binarised final frame with fingertip markers and critical-radius circle.')
    return 'Saved output figure from the simulation walkthrough.'


def render_notebook(notebook):
    exporter = HTMLExporter(template_name='classic', template_file='base.html.j2')
    body, _ = exporter.from_notebook_node(notebook)
    soup = BeautifulSoup(body, 'html.parser')
    assert not soup.find('script'), 'Notebook must not embed executable scripts.'
    rendered = soup.select('.cell')
    assert len(rendered) == len(notebook.cells)
    section_by_cell = {i: (anchor, title) for i, anchor, title in SECTIONS}
    code_number = 0
    for index, (cell, source) in enumerate(zip(rendered, notebook.cells, strict=True)):
        cell['id'] = f'notebook-cell-{index}'
        cell['data-source-cell'] = str(index)
        if index in section_by_cell:
            anchor, title = section_by_cell[index]
            heading = cell.find(re.compile(r'^h[1-6]$'))
            if heading:
                heading['id'] = anchor
                old_link = heading.select_one('a.anchor-link')
                if old_link:
                    old_link['href'] = '#' + anchor
                    old_link['aria-label'] = 'Link to ' + title
            else:
                heading = soup.new_tag('h3', id=anchor)
                heading.string = title
                cell.insert(0, heading)
            heading['tabindex'] = '-1'
        if source.cell_type != 'code':
            continue
        code_number += 1
        cell['data-code-cell'] = str(code_number)
        code_anchor = soup.new_tag('span', id=f'cell-{code_number}')
        code_anchor['class'] = 'notebook-cell-anchor'
        cell.insert(0, code_anchor)
        area = cell.select_one('.input_area')
        area['tabindex'] = '0'
        area['role'] = 'region'
        area['aria-label'] = f'Saved source, code cell {code_number}'
        area.pre['data-source-cell'] = str(index)
        for output_index, output in enumerate(cell.select('.output_area')):
            output['data-source-output'] = f'{index}:{output_index}'
            subarea = output.select_one('.output_subarea')
            if subarea:
                subarea['tabindex'] = '0'
                subarea['role'] = 'region'
                subarea['aria-label'] = f'Saved output {output_index + 1}, code cell {code_number}'
        for table in cell.select('table'):
            table['aria-label'] = f'Saved table, code cell {code_number}'
        for image_index, img in enumerate(cell.select('img')):
            img['alt'] = image_description(index, image_index)
            if img.get('src', '').startswith('data:image/png;base64,'):
                raw = base64.b64decode(img['src'].split(',', 1)[1])
                img['width'], img['height'] = struct.unpack('>II', raw[16:24])
        for output in list(cell.select('.output_area')):
            pre = output.select_one('.output_subarea pre')
            if not pre or len(pre.get_text().splitlines()) < 35:
                continue
            details = soup.new_tag('details')
            details['class'] = 'saved-log'
            summary = soup.new_tag('summary')
            summary.string = f'Saved output · {len(pre.get_text().splitlines()):,} lines · expand to read'
            details.append(summary)
            output.wrap(details)
    # Local notebook URLs were authored relative to the repository root.
    for link in soup.select('a[href]'):
        href = link['href']
        if not href.startswith('#') and not urlsplit(href).scheme:
            link['href'] = GIT + href.removeprefix('./')
        if urlsplit(link['href']).scheme in {'http', 'https'}:
            link['target'] = '_blank'
            link['rel'] = 'noopener noreferrer'
    for image in soup.select('.text_cell img[src]'):
        path = image['src'].removeprefix('./')
        if path == 'docs/hele-shaw-cells.png':
            image['src'] = 'assets/hele-shaw-cells.png'
            raw = (REPO / path).read_bytes()
            image['width'], image['height'] = struct.unpack('>II', raw[16:24])
            image['alt'] = 'Reference simulation image at approximately 10 seconds; not an experimental photograph.'
        elif not urlsplit(path).scheme:
            raise ValueError(f'Unresolved notebook image: {path}')
    equations = render_math(soup)
    manifest = source_manifest(notebook)
    manifest['equations'] = equations
    contents = ''.join(f'<li><a href="#{anchor}">{html.escape(title)}</a></li>'
                       for _, anchor, title in SECTIONS
                       if anchor not in {'governing-equations', 'gap-averaged-model',
                                         'initial-boundary-conditions', 'dimensionless-numbers',
                                         'reference-result', 'solver-numerics', 'compare-reference'})
    page = f'''<!doctype html>
<html lang="en" class="document-view">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Saved simulation walkthrough — Simulation-Benchmarks/hele-shaw-cells-example</title>
<link rel="stylesheet" href="../tokens.css"><link rel="stylesheet" href="../style.css">
<link rel="stylesheet" href="notebook.css"></head>
<body data-view="notebook">
<header><a class="brand" href="../index.html#overview">Simulation-Benchmarks/<wbr>hele-shaw-cells-example</a>
<nav aria-label="Main navigation"><a href="../index.html#overview">Semantic Model</a><a href="../index.html#workflows" aria-current="page">Workflows</a><a href="../index.html#nfdi4ing">NFDI4Ing Use Cases</a></nav></header>
<main id="notebook-page">
<nav class="notebook-actions" aria-label="Notebook navigation"><a href="../index.html#workflow-inspect-results">← Back to workflow</a><a href="#contents">Contents</a><a href="{GIT}notebooks/Simulation_Walkthrough.ipynb" target="_blank" rel="noopener noreferrer">Notebook source in Git ↗</a></nav>
<p class="notebook-status">Saved notebook run · {manifest['executedCodeCellCount']} executed code cells · {manifest['savedImageCount']} saved figures · Read-only view</p>
<aside class="notebook-evidence" aria-label="About this saved evidence"><strong>Evidence from an earlier run</strong>
<p>This page preserves the notebook’s saved code, outputs and commentary. Building this view did not run a simulation. Execution counts are not sequential because a figure cell was rerun.</p>
<p>Three metrics are missing in the saved run. Configuration 1 reports four passes and three skipped checks; configurations 2 and 3 include failures against configuration 1’s baseline. Those varied configurations are sensitivity cases, not reference regressions.</p>
<p>Some original commentary is stale: the saved output reports 300 time steps and 25,600 cells for configuration 2. The RO-Crate output demonstrates local packaging; it does not establish an external upload. Repository code and recorded outputs take precedence over conflicting prose.</p></aside>
<nav class="notebook-contents" aria-label="Saved notebook contents"><h2 id="contents" tabindex="-1">Contents</h2><ol>{contents}</ol></nav>
{soup}
</main></body></html>\n'''
    # Preserve saved trailing spaces as HTML entities without introducing Git
    # whitespace errors. Decoded output text remains byte-for-byte equivalent.
    page = re.sub(r'[ \t]+(?=\n)',
                  lambda match: ''.join('&#32;' if char == ' ' else '&#9;'
                                        for char in match.group()), page)
    return page, manifest


def validate_view(notebook, page: str, manifest: dict) -> dict:
    """Independently compare the published code and outputs with the notebook."""
    soup = BeautifulSoup(page, 'html.parser')
    expected = source_manifest(notebook)
    for key, value in expected.items():
        assert manifest[key] == value, f'Notebook manifest mismatch: {key}'
    assert not soup.find('script'), 'Published notebook must not contain scripts.'
    assert not soup.select('link[href^="http"]'), 'Styles must be local.'
    code_cells = [c for c in notebook.cells if c.cell_type == 'code']
    assert len(soup.select('.code_cell')) == len(code_cells)
    assert len(soup.select('.output_area')) == expected['outputCount']
    rendered_images = []
    rendered_tables = 0
    for index, cell in enumerate(notebook.cells):
        if cell.cell_type != 'code':
            continue
        source = soup.select_one(f'.input_area pre[data-source-cell="{index}"]')
        assert source is not None
        assert source.get_text().rstrip('\n') == cell.source.rstrip('\n'), f'Code changed in source cell {index}'
        rendered_cell = soup.select_one(f'.code_cell[data-source-cell="{index}"]')
        assert f'[{cell.execution_count}]' in rendered_cell.select_one('.input_prompt').get_text()
        for output_index, output in enumerate(cell.outputs):
            area = soup.select_one(f'.output_area[data-source-output="{index}:{output_index}"]')
            assert area is not None
            if output.output_type == 'stream':
                assert area.select_one('pre').get_text() == strip_ansi(output.text), f'Stream changed in {index}:{output_index}'
            elif 'image/png' in output.get('data', {}):
                image = area.select_one('img')
                raw = base64.b64decode(image['src'].split(',', 1)[1])
                expected_raw = base64.b64decode(cell_text(output.data['image/png']))
                assert raw == expected_raw, f'Figure changed in {index}:{output_index}'
                rendered_images.append(digest(raw))
            elif 'text/html' in output.get('data', {}):
                original_html = BeautifulSoup(cell_text(output.data['text/html']), 'html.parser')
                for original, rendered in zip(original_html.select('table'), area.select('table'), strict=True):
                    assert list(original.stripped_strings) == list(rendered.stripped_strings), f'Table changed in {index}:{output_index}'
                    rendered_tables += 1
            elif 'text/plain' in output.get('data', {}):
                assert area.select_one('pre').get_text().rstrip('\n') == strip_ansi(cell_text(output.data['text/plain'])).rstrip('\n')
    assert rendered_images == [im['sha256'] for im in expected['images']]
    for section in expected['sections']:
        assert soup.find(id=section['anchor']), f'Missing notebook anchor: {section["anchor"]}'
    assert [math['data-tex'] for math in soup.select('math[data-tex]')] == [eq['tex'] for eq in manifest['equations']]
    for image in soup.select('img[src]'):
        assert not image['src'].startswith(('http:', 'https:')), 'Notebook images must be saved locally.'
    return {'codeCellsVerified': len(code_cells), 'outputsVerified': expected['outputCount'],
            'savedImagesVerified': len(rendered_images), 'tablesVerified': rendered_tables,
            'equationsRendered': len(manifest['equations']), 'executedByBuild': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Validate committed view without rewriting files.')
    args = parser.parse_args()
    notebook = nbformat.read(SOURCE, as_version=4)
    if args.check:
        manifest = json.loads(MANIFEST.read_text())
        assert manifest['viewSha256'] == digest(VIEW.read_bytes()), 'Notebook HTML hash mismatch.'
        for asset, expected_hash in manifest['assets'].items():
            assert digest((SITE / asset).read_bytes()) == expected_hash
        report = validate_view(notebook, VIEW.read_text(), manifest)
    else:
        page, manifest = render_notebook(notebook)
        report = validate_view(notebook, page, manifest)
        VIEW.parent.mkdir(parents=True, exist_ok=True)
        assets = VIEW.parent / 'assets'
        assets.mkdir(exist_ok=True)
        shutil.copyfile(REPO / 'docs/hele-shaw-cells.png', assets / 'hele-shaw-cells.png')
        VIEW.write_text(page)
        manifest['viewSha256'] = digest(VIEW.read_bytes())
        manifest['assets'] = {str(path.relative_to(SITE)): digest(path.read_bytes())
                              for path in [assets / 'hele-shaw-cells.png', VIEW.parent / 'notebook.css']}
        manifest['verification'] = report
        MANIFEST.parent.mkdir(exist_ok=True)
        MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
