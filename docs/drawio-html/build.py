#!/usr/bin/env python3
"""Rebuild or check this portable draw.io example; Python standard library only.

SPDX-FileCopyrightText: 2026 Vasiliy Seibert
SPDX-License-Identifier: MIT
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def signature(element):
    return (element.tag, tuple(sorted(element.attrib.items())),
            (element.text or '').strip(), tuple(signature(c) for c in element))


def outputs(folder=HERE):
    """Validate original IDs/interpretations and generate portable navigation."""
    original = (folder / 'Validation.drawio').read_bytes()
    mapping = json.loads((folder / 'drawio-links.json').read_text())
    meta, links = mapping['meta'], mapping['links']
    require(sha(original) == meta['sourceSha256'],
            'Original diagram differs from its recorded hash; review the source and crosswalk together.')
    require(b'<!DOCTYPE' not in original.upper(), 'DTD declarations are not supported.')
    root = ET.fromstring(original)
    models = root.findall('.//mxGraphModel')
    require(len(models) == 1, 'This example requires one uncompressed mxGraphModel page.')
    require(models[0].get('math', '0') == '0', 'This offline example does not include math typesetting.')
    all_cells = root.findall('.//mxCell')
    ids = [cell.get('id') for cell in all_cells]
    require(all(ids) and len(ids) == len(set(ids)), 'Source cell IDs must be present and unique.')
    cells = {cell.get('id'): cell for cell in all_cells
             if cell.get('vertex') == '1' or cell.get('edge') == '1'}
    require(set(links) == set(cells), 'Every original vertex and edge needs exactly one mapping entry.')
    crosswalk_bytes = (folder / 'diagram-crosswalk.json').read_bytes()
    require(sha(crosswalk_bytes) == meta['crosswalkSha256'], 'Semantic crosswalk differs from the recorded snapshot.')
    crosswalk = json.loads(crosswalk_bytes)
    require(crosswalk['meta']['sha256'] == sha(original), 'Crosswalk describes another diagram.')
    vertices = {entry['diagramId']: entry for entry in crosswalk['vertices']}
    edges = {entry['diagramId']: entry for entry in crosswalk['edges']}
    require(set(vertices) | set(edges) == set(cells), 'Crosswalk coverage differs from the drawing.')
    base = meta['publishedBaseUrl']
    require(base.startswith('https://') and base.endswith('/'), 'Use an HTTPS publishedBaseUrl ending in /.')
    resolved = copy.deepcopy(links)
    for identifier, cell in cells.items():
        entry = resolved[identifier]
        is_edge = cell.get('edge') == '1'
        require(entry['diagramId'] == identifier, f'Changed cell identity: {identifier}')
        require(entry['type'] == ('edge' if is_edge else 'vertex'), f'Wrong cell type: {identifier}')
        require(entry['originalValue'] == cell.get('value', ''), f'Changed original label: {identifier}')
        record = edges[identifier] if is_edge else vertices[identifier]
        require(entry['normalizedLabel'] == record['normalizedLabel'], f'Changed semantic label: {identifier}')
        require(entry['originalLabel'] == entry['label'] == record['originalLabel'] and
                entry['rawLabel'] == cell.get('value', ''), f'Changed readable original label: {identifier}')
        if is_edge:
            for key, attr in [('sourceDiagramId', 'source'), ('targetDiagramId', 'target')]:
                require(entry[key] == cell.get(attr) == record[key], f'Changed arrow endpoint: {identifier}')
            for key in ('predicate', 'status', 'asserted', 'directionNormalized', 'mappedSource', 'mappedTarget', 'reviewNote'):
                require(entry[key] == record[key], f'Changed semantic interpretation {key}: {identifier}')
            require(entry['relationshipId'] == identifier and entry['relationId'] == record['edgeId'],
                    f'Changed relationship binding: {identifier}')
        else:
            require(entry['entityId'] == record['entityId'], f'Changed semantic entity: {identifier}')
            require(entry['status'] == record['status'] and entry['kind'] == record['kind'],
                    f'Changed semantic status or kind: {identifier}')
        require(entry['target'] in ('_self', '_blank'), f'Unsupported link target: {identifier}')
        require(isinstance(entry['url'], str) and entry['url'].strip(), f'Missing URL: {identifier}')
        url = urljoin(base, entry['url'])
        parsed = urlsplit(url)
        require(parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password,
                f'Link must resolve to an HTTPS URL without credentials: {identifier}')
        entry['url'] = url

    # Native hyperlink wrappers, with a lossless round-trip check. This mirrors
    # docs/semantic/tools/build_drawio.py; it never writes the original file.
    linked = copy.deepcopy(root)
    for parent in linked.iter():
        for cell in list(parent):
            identifier = cell.get('id')
            if cell.tag != 'mxCell' or identifier not in resolved:
                continue
            entry = resolved[identifier]
            attrs = {'id': identifier, 'link': entry['url'], 'linkTarget': entry['target']}
            if 'value' in cell.attrib:
                attrs['label'] = cell.attrib.pop('value')
            del cell.attrib['id']
            wrapper = ET.Element('UserObject', attrs)
            position = list(parent).index(cell)
            parent.remove(cell)
            wrapper.append(cell)
            parent.insert(position, wrapper)
    normalized = copy.deepcopy(linked)
    for parent in normalized.iter():
        for wrapper in list(parent):
            if wrapper.tag != 'UserObject':
                continue
            cell = wrapper[0]
            identifier = wrapper.get('id')
            cell.set('id', identifier)
            if 'value' in cells[identifier].attrib:
                cell.set('value', wrapper.get('label', ''))
            position = list(parent).index(wrapper)
            parent.remove(wrapper)
            parent.insert(position, cell)
    require(signature(normalized) == signature(root), 'Hyperlink wrappers changed the original drawing.')

    linked_bytes = ET.tostring(linked, encoding='utf-8', xml_declaration=True) + b'\n'
    portable_meta = dict(meta, sourceDownload='Validation.drawio', linkedDownload='Validation.linked.drawio',
                         crosswalkPath='diagram-crosswalk.json', linksSha256=sha(json_bytes(resolved)),
                         linkedSha256=sha(linked_bytes))
    portable_meta['upstreamModel'] = {
        'url': urljoin(base, portable_meta.pop('modelPath')),
        'sha256': portable_meta.pop('modelSha256'),
        'scope': 'Atlas snapshot used to generate this mapping; not bundled in the portable folder.',
    }
    payload = {'xml': original.decode('utf-8'), 'meta': portable_meta, 'links': resolved}
    data = 'window.HELE_SHAW_DRAWIO = ' + json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + ';\n'
    fields = ['diagramId', 'type', 'originalLabel', 'normalizedLabel', 'entityId', 'sourceDiagramId',
              'targetDiagramId', 'predicate', 'status', 'asserted', 'directionNormalized', 'url']
    table = io.StringIO(newline='')
    writer = csv.DictWriter(table, fieldnames=fields, extrasaction='ignore', lineterminator='\n')
    writer.writeheader()
    writer.writerows(resolved[key] for key in cells)
    generated = {'data.js': data.encode(), 'mapping.csv': table.getvalue().encode(),
                 'Validation.linked.drawio': linked_bytes}
    vendor = folder / 'vendor/drawio/29.6.6'
    provenance = json.loads((vendor / 'provenance.json').read_text())
    renderer_hash = sha((vendor / 'viewer-static.min.js').read_bytes())
    require(renderer_hash == provenance['sha256'], 'Official renderer differs from its pinned checksum.')
    sources = ['Validation.drawio', 'drawio-links.json', 'diagram-crosswalk.json', 'index.html',
               'viewer.js', 'style.css', 'tokens.css', 'drawio-viewer.js', 'build.py', 'README.md', 'ATTRIBUTION.md']
    sources.extend(str(path.relative_to(folder)) for path in sorted(vendor.iterdir()) if path.is_file())
    hashes = {name: sha((folder / name).read_bytes()) for name in sources}
    hashes.update({name: sha(content) for name, content in generated.items()})
    generated['manifest.json'] = json_bytes({
        'version': 1, 'sourceSha256': sha(original), 'vertexCount': len(vertices), 'edgeCount': len(edges),
        'graphicalCells': len(cells), 'allMxCells': len(all_cells), 'linksVerified': len(resolved),
        'sourceUnchanged': True, 'linkedXmlNormalizesToOriginal': True,
        'rendererVersion': '29.6.6', 'rendererSha256': renderer_hash,
        'publishedBaseUrl': base, 'files': hashes,
    })
    return generated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Verify generated files without writing them.')
    args = parser.parse_args()
    try:
        generated = outputs()
        if args.check:
            stale = [name for name, content in generated.items()
                     if not (HERE / name).is_file() or (HERE / name).read_bytes() != content]
            require(not stale, 'Generated files need rebuilding: ' + ', '.join(stale))
        else:
            for name, content in generated.items():
                (HERE / name).write_bytes(content)
    except (ValueError, KeyError, OSError, ET.ParseError) as error:
        parser.exit(1, f'Cannot build the drawing package: {error}\n')
    report = json.loads(generated['manifest.json'])
    print(('Verified' if args.check else 'Built') +
          f" portable drawing: {report['vertexCount']} vertices, {report['edgeCount']} edges, "
          f"{report['linksVerified']} mapped links; original unchanged.")


if __name__ == '__main__':
    main()
