#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Vasiliy Seibert
# SPDX-License-Identifier: MIT
"""Validate the original draw.io view and its portable linked derivative.

The renderer consumes the original XML, not an inferred SVG reconstruction.
This independent check compares complete XML trees, including nested waypoints,
and only permits native draw.io link wrappers in the downloadable derivative.
It makes no claim about the scientific validity of the source diagram.
"""
from __future__ import annotations

import copy
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import quote, unquote, urljoin, urlsplit
import xml.etree.ElementTree as ET

SITE = Path(__file__).resolve().parents[1]
REPO = SITE.parents[1]
SOURCE_SHA256 = '182b574888e044685ed66d6505eed993ff3187d04fa58af9ade6e0c98b93f1ab'
SOURCE_VERTEX_COUNT = 112
SOURCE_EDGE_COUNT = 100
JS_PREFIX = 'window.HELE_SHAW_DRAWIO = '
RENDERER_VERSION = '29.6.6'
RENDERER_SHA256 = '997b577dfa6285d0efc0e658295f92c72b84680af0b0d43ab0e0effe7b9902bc'
RENDERER_BYTES = 3725506
ONTOLOGY_BASE = 'https://nfdi4ing.pages.rwth-aachen.de/metadata4ing/metadata4ing/'
ONTOLOGY_DEFINITIONS = {
    'm4i:Numerical Variable': ONTOLOGY_BASE + '#NumericalVariable',
    'm4i:ProcessingStep': ONTOLOGY_BASE + '#ProcessingStep',
    'm4i:Method': ONTOLOGY_BASE + '#Method',
    'm4i:Tool': ONTOLOGY_BASE + '#Tool',
    'm4i:VariableSet': ONTOLOGY_BASE + '#VariableSet',
    'cr:Field': ONTOLOGY_BASE + '#http://mlcommons.org/croissant/Field',
    'qudt:Quantity Kind': 'https://qudt.org/schema/qudt/QuantityKind',
    'qudt:Unit': 'https://qudt.org/schema/qudt/Unit',
    'schema:SoftwareApplication': 'https://schema.org/SoftwareApplication',
}


class Anchors(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        self.ids.update(value for name, value in attrs if name == 'id')


class PageResources(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.styles = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == 'script':
            self.scripts.append(attributes)
        if tag == 'link' and 'stylesheet' in attributes.get('rel', '').split():
            self.styles.append(attributes)


def validate_offline_renderer(site: Path = SITE, index_text=None,
                              original=None, offline_text=None) -> dict:
    """Check the pinned official bundle and the offline bootstrap contract.

    This static regression guard complements the browser's network smoke test;
    it does not claim to simulate all dynamic requests from arbitrary diagrams.
    Only this source's math="0" input is supported by the offline configuration.
    """
    vendor = site / 'vendor/drawio' / RENDERER_VERSION
    provenance = json.loads((vendor / 'provenance.json').read_text())
    bundle = (vendor / 'viewer-static.min.js').read_bytes()
    assert provenance['version'] == RENDERER_VERSION, 'Official renderer version changed without review.'
    assert provenance['sha256'] == sha256(bundle) == RENDERER_SHA256, 'Official renderer bytes differ from pinned provenance.'
    assert provenance['bytes'] == len(bundle) == RENDERER_BYTES, 'Official renderer byte count differs from provenance.'
    assert provenance['upstream'] == 'https://github.com/jgraph/drawio-desktop/releases/tag/v29.6.6', 'Unexpected renderer upstream.'
    for name in ('LICENSE', 'PAKO-LICENSE', 'PAKO-ZLIB-NOTICE', 'SHAPES-LICENSE', 'SPIN-LICENSE', 'STENCILS-LICENSE'):
        assert (vendor / name).is_file(), f'Missing official bundle license notice: {name}'
    original = original if original is not None else (site / 'source/Validation.drawio').read_bytes()
    diagram_models = list(ET.fromstring(original).iter('mxGraphModel'))
    assert diagram_models and all(model.get('math') == '0' for model in diagram_models), 'Offline original diagram must declare math="0".'
    resources = PageResources()
    resources.feed(index_text if index_text is not None else (site / 'index.html').read_text())
    scripts = [script.get('src') for script in resources.scripts]
    assert all(scripts), 'Atlas bootstrap must use explicit local scripts.'
    assert len(scripts) == len(set(scripts)), 'Duplicate bootstrap scripts.'
    resource_paths = scripts + [style.get('href') for style in resources.styles]
    for path in resource_paths:
        assert path, 'Stylesheet reference is empty.'
        parsed = urlsplit(path)
        assert not parsed.scheme and not parsed.netloc and not parsed.path.startswith('/'), f'Atlas resource must be local: {path}'
        destination = (site / unquote(parsed.path)).resolve()
        assert destination.is_relative_to(site.resolve()), f'Atlas resource escapes published directory: {path}'
        assert destination.is_file(), f'Missing local atlas resource: {path}'
    prefix = f'vendor/drawio/{RENDERER_VERSION}/'
    bootstrap = [prefix + 'offline-config.js', prefix + 'viewer-static.min.js', 'drawio-viewer.js', 'app.js']
    assert all(path in scripts for path in bootstrap), 'Required offline renderer bootstrap script is missing.'
    assert [scripts.index(path) for path in bootstrap] == sorted(scripts.index(path) for path in bootstrap), 'Offline config must precede official viewer, adapter, and app.'
    for script in resources.scripts:
        assert 'defer' in script and 'async' not in script, 'Bootstrap scripts must preserve deferred document order.'
    for path in ('data/model.js', 'data/graphs.js', 'data/drawio.js'):
        assert path in scripts and scripts.index(path) < scripts.index('app.js'), f'Atlas data must load before app: {path}'
    offline = offline_text if offline_text is not None else (vendor / 'offline-config.js').read_text()
    # This sentinel is required because the byte-pinned official viewer invokes
    # Editor.initMath even when mxGraphModel has math="0".
    assert re.search(r"typeof\s+window\.MathJax\s*===\s*['\"]undefined['\"]", offline), 'Offline MathJax guard is missing.'
    assert re.search(r'window\.MathJax\s*=\s*Object\.freeze\(\s*\{\s*heleShawDisabled\s*:\s*true\s*\}\s*\)', offline), 'Offline MathJax sentinel is missing.'
    adapter = (site / 'drawio-viewer.js').read_text()
    assert 'window.MathJax?.heleShawDisabled' in adapter and 'mxGraphModel[math="1"]' in adapter, 'Offline adapter must reject math-enabled diagrams.'
    assert "window.urlParams?.math === '1'" in adapter, 'Offline adapter must reject the URL math override.'
    return {'officialRendererVersion': RENDERER_VERSION, 'officialRendererSha256': RENDERER_SHA256,
            'officialRendererBytes': len(bundle), 'localBootstrapResources': len(resource_paths),
            'offlineBootstrapOrderVerified': True, 'sourceMathDisabled': True}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_projection(path: Path) -> dict:
    text = path.read_text()
    assert text.startswith(JS_PREFIX), 'drawio.js has an unexpected browser global.'
    assert text.rstrip().endswith(';'), 'drawio.js has an invalid assignment.'
    return json.loads(text[len(JS_PREFIX):].strip().removesuffix(';'))


def cell_index(root: ET.Element) -> dict:
    cells = list(root.iter('mxCell'))
    indexed = {cell.get('id'): cell for cell in cells}
    assert None not in indexed, 'Every mxCell requires an ID after link normalization.'
    assert len(indexed) == len(cells), 'Duplicate mxCell IDs.'
    return indexed


def canonical_tree(element: ET.Element):
    """Ignore XML indentation and attribute order, but preserve all source data."""
    text = element.text or ''
    tail = element.tail or ''
    return (element.tag, tuple(sorted(element.attrib.items())),
            text if text.strip() else '', tail if tail.strip() else '',
            tuple(canonical_tree(child) for child in element))


def normalize_linked(root: ET.Element) -> tuple[ET.Element, dict]:
    normalized = copy.deepcopy(root)
    links = {}
    for parent in list(normalized.iter()):
        for child in list(parent):
            if child.tag not in {'UserObject', 'object'}:
                continue
            assert set(child.attrib) <= {'id', 'label', 'link', 'linkTarget', 'tooltip'}, 'Unexpected metadata in draw.io link wrapper.'
            assert len(child) == 1 and child[0].tag == 'mxCell', 'A link wrapper must contain exactly one mxCell.'
            assert not (child.text or '').strip(), 'Unexpected wrapper content.'
            cell = child[0]
            identifier = child.get('id')
            assert identifier and identifier not in links, 'Duplicate or missing linked cell ID.'
            assert child.get('link'), f'Missing draw.io link: {identifier}'
            assert not cell.get('id') or cell.get('id') == identifier, f'Conflicting linked ID: {identifier}'
            assert not cell.get('value') or cell.get('value') == child.get('label', ''), f'Conflicting linked label: {identifier}'
            cell.set('id', identifier)
            if 'label' in child.attrib:
                cell.set('value', child.get('label', ''))
            links[identifier] = child.get('link')
            # Link wrappers may format the surrounding XML differently, but
            # neither their original cells nor geometry are changed.
            cell.tail = child.tail
            position = list(parent).index(child)
            parent.remove(child)
            parent.insert(position, cell)
    return normalized, links


def verify_linked_xml(original: bytes, linked: bytes) -> dict:
    original_root = ET.fromstring(original)
    normalized, links = normalize_linked(ET.fromstring(linked))
    assert canonical_tree(original_root) == canonical_tree(normalized), 'Linked draw.io changed original labels, styles, endpoints, geometry, or structure.'
    original_cells = cell_index(original_root)
    graphical_ids = {identifier for identifier, cell in original_cells.items()
                     if cell.get('vertex') == '1' or cell.get('edge') == '1'}
    assert set(links) == graphical_ids, 'Linked draw.io must link every vertex and edge exactly once.'
    return links


def validate_runtime_url(url: str, entry: dict, entities: dict, relationships: dict,
                         source_manifest: dict, site: Path) -> None:
    assert isinstance(url, str) and url, 'A diagram link needs a URL.'
    assert not url.startswith(('javascript:', 'data:', '//')), 'Unsafe diagram link.'
    if 'relationshipId' in entry:
        expected = '#relationship/' + quote(entry['relationshipId'], safe='')
        assert url == expected, f'Wrong relationship route for {entry["relationshipId"]}'
        assert entry['relationshipId'] in relationships, 'Relationship route is unknown.'
        return
    entity_id = entry['entityId']
    entity = entities[entity_id]
    expected = '#overview/' + quote(entity_id, safe='')
    if url.startswith('#'):
        assert url == expected, f'Wrong entity route for {entity_id}'
        return
    if entry.get('linkKind') == 'source' and entry.get('sourcePath'):
        revision, path = entry['sourceRevision'], entry['sourcePath']
        assert revision == source_manifest['revision'], 'Source link uses an unreviewed revision.'
        assert not Path(path).is_absolute() and '..' not in Path(path).parts, 'Source path escapes repository.'
        expected = f'{source_manifest["repository"]}/blob/{revision}/{path}'
        assert url == expected, f'Source URL differs from its pinned path: {entity_id}'
        subprocess.run(['git', 'cat-file', '-e', f'{revision}:{path}'],
                       cwd=site.parents[1], check=True, stdout=subprocess.DEVNULL)
        return
    if entry.get('linkKind') == 'ontology-definition':
        assert url == ONTOLOGY_DEFINITIONS.get(entry['originalLabel']), f'Unexpected ontology definition: {entity_id}'
        return
    expected_urls = {source['url'] for source in entity.get('sources', [])}
    expected_urls.update(entity[key] for key in ('previewUrl', 'launchUrl') if entity.get(key))
    if entry.get('linkKind') == 'saved-evidence':
        notebook = json.loads((site / 'data/notebook-manifest.json').read_text())
        expected_urls.update(section['previewUrl'] for section in notebook['sections'])
        expected_urls.add(notebook['view'])
    assert url in expected_urls, f'Link is not a source or verified saved preview of {entity_id}'
    parsed = urlsplit(url)
    if parsed.scheme:
        assert parsed.scheme == 'https', f'Non-HTTPS source for {entity_id}'
        if '/blob/' in parsed.path and parsed.netloc == 'github.com':
            known = {record['url'] for record in source_manifest['files']}
            assert url.split('#', 1)[0] in known, f'Unverified pinned source for {entity_id}'
        return
    target = (site / unquote(parsed.path)).resolve()
    assert target.is_relative_to(site.resolve()), f'Link escapes the deployed site: {url}'
    assert target.is_file(), f'Local diagram link is missing: {url}'
    if parsed.fragment and target.suffix == '.html':
        anchors = Anchors()
        anchors.feed(target.read_text())
        assert unquote(parsed.fragment) in anchors.ids, f'Notebook section link is missing: {url}'


def validate_payload(original: bytes, copied: bytes, linked: bytes,
                     projection: dict, manifest: dict, crosswalk: dict,
                     model: dict, sources: dict, site: Path = SITE) -> dict:
    source_hash = sha256(original)
    assert source_hash == SOURCE_SHA256, 'The supplied original Validation.drawio changed.'
    assert copied == original, 'Published original draw.io is not byte-identical.'
    assert projection['xml'].encode() == original, 'Runtime XML must be the exact supplied original.'
    assert projection['meta'] == manifest['meta'], 'Runtime and link manifest metadata differ.'
    assert projection['links'] == manifest['links'], 'Runtime and manifest link maps differ.'
    assert projection['meta']['sourceSha256'] == source_hash, 'Runtime source hash differs.'
    assert projection['meta']['sourceBytes'] == len(original), 'Runtime original byte count differs.'
    assert crosswalk['meta']['sha256'] == source_hash == model['meta']['diagramSha256'], 'Source hash differs from semantic crosswalk.'
    root = ET.fromstring(original)
    cells = cell_index(root)
    vertices = {identifier: cell for identifier, cell in cells.items() if cell.get('vertex') == '1'}
    edges = {identifier: cell for identifier, cell in cells.items() if cell.get('edge') == '1'}
    assert len(vertices) == SOURCE_VERTEX_COUNT, 'Original vertex count changed.'
    assert len(edges) == SOURCE_EDGE_COUNT, 'Original edge count changed.'
    assert projection['meta']['vertexCount'] == len(vertices), 'Runtime vertex count differs.'
    assert projection['meta']['edgeCount'] == len(edges), 'Runtime edge count differs.'
    assert projection['meta']['cellCount'] == len(vertices) + len(edges), 'Runtime graphical cell count differs.'
    links = projection['links']
    assert set(links) == set(vertices) | set(edges), 'Runtime must link every original vertex and edge exactly once.'
    entity_map = {entity['id']: entity for entity in model['entities']}
    relation_map = {entry['diagramId']: entry for entry in crosswalk['edges']}
    vertex_map = {entry['diagramId']: entry for entry in crosswalk['vertices']}
    semantic_edges = {entry['id']: entry for entry in model['edges']}
    assert set(vertex_map) == set(vertices) and set(relation_map) == set(edges), 'Crosswalk IDs differ from original draw.io.'
    for identifier, cell in vertices.items():
        entry = links[identifier]
        assert entry['type'] == 'vertex', f'Incorrect draw.io cell kind: {identifier}'
        assert entry['entityId'] == vertex_map[identifier]['entityId'], f'Wrong entity binding: {identifier}'
        assert entry['entityId'] in entity_map, f'Unknown entity: {identifier}'
        assert entry['originalLabel'] == vertex_map[identifier]['originalLabel'], f'Changed readable vertex label: {identifier}'
        assert entry['normalizedLabel'] == vertex_map[identifier]['normalizedLabel'], f'Changed mapped vertex label: {identifier}'
        verify_linked_entry(identifier, cell, entry)
        validate_runtime_url(entry['url'], entry, entity_map, relation_map, sources, site)
    for identifier, cell in edges.items():
        entry, relation = links[identifier], relation_map[identifier]
        assert entry['type'] == 'edge', f'Incorrect draw.io cell kind: {identifier}'
        assert entry['relationshipId'] == identifier, f'Wrong original relationship ID: {identifier}'
        assert entry['relationId'] == relation['edgeId'] in semantic_edges, f'Wrong RDF relationship binding: {identifier}'
        assert entry['sourceDiagramId'] == cell.get('source'), f'Changed source endpoint: {identifier}'
        assert entry['targetDiagramId'] == cell.get('target'), f'Changed target endpoint: {identifier}'
        assert entry['originalValue'] == cell.get('value', ''), f'Changed original relationship label: {identifier}'
        assert entry['originalLabel'] == relation['originalLabel'], f'Changed readable relationship label: {identifier}'
        assert entry['normalizedLabel'] == relation['normalizedLabel'], f'Changed mapped relationship label: {identifier}'
        for key in ('predicate', 'status', 'asserted', 'directionNormalized', 'mappedSource', 'mappedTarget', 'reviewNote'):
            assert entry[key] == relation[key], f'Changed relationship interpretation: {identifier}: {key}'
        assert entry['sourceEntityId'] == relation['source'], f'Wrong source entity: {identifier}'
        assert entry['targetEntityId'] == relation['target'], f'Wrong target entity: {identifier}'
        verify_linked_entry(identifier, cell, entry)
        validate_runtime_url(entry['url'], entry, entity_map, relation_map, sources, site)
    derivative_links = verify_linked_xml(original, linked)
    publication_root = model['meta']['namespace']
    assert publication_root.startswith('https://') and publication_root.endswith('/'), 'Invalid publication root.'
    for identifier, href in derivative_links.items():
        expected = urljoin(publication_root, links[identifier]['url'])
        assert href == expected, f'Portable linked draw.io has wrong destination: {identifier}'
        assert urlsplit(href).scheme == 'https', f'Derivative link is not portable: {identifier}'
    canonical_links = (json.dumps(links, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()
    assert projection['meta']['linksSha256'] == sha256(canonical_links), 'Link-map digest differs.'
    assert projection['meta']['linkedSha256'] == sha256(linked), 'Linked derivative digest differs.'
    assert projection['meta']['publishedBaseUrl'] == publication_root, 'Portable link base differs from site publication root.'
    assert projection['meta']['modelSha256'] == sha256((site / 'data/model.json').read_bytes()), 'Draw.io model digest differs.'
    assert projection['meta']['crosswalkSha256'] == sha256((site / 'source/diagram-crosswalk.json').read_bytes()), 'Draw.io crosswalk digest differs.'
    assert projection['meta']['repositoryRevision'] == model['meta']['revision'] == sources['revision'], 'Draw.io source revision differs.'
    return {'sourceSha256': source_hash, 'sourceUnchanged': True,
            'vertexCount': len(vertices), 'edgeCount': len(edges),
            'cellCount': len(cells), 'linksVerified': len(links),
            'originalGeometryPreserved': True, 'runtimeUsesOriginalXml': True,
            'linkedDerivativePortable': True}


def verify_linked_entry(identifier, cell, entry):
    assert entry.get('target') in {'_self', '_blank'}, f'Invalid link target: {identifier}'
    if 'originalValue' in entry:
        assert entry['originalValue'] == cell.get('value', ''), f'Changed original label: {identifier}'
    if 'diagramId' in entry:
        assert entry['diagramId'] == identifier, f'Changed diagram link ID: {identifier}'


def load_payload(site: Path = SITE, repo: Path = REPO) -> dict:
    return {
        'original': (repo / 'Validation.drawio').read_bytes(),
        'copied': (site / 'source/Validation.drawio').read_bytes(),
        'linked': (site / 'source/Validation.linked.drawio').read_bytes(),
        'projection': read_projection(site / 'data/drawio.js'),
        'manifest': json.loads((site / 'source/drawio-links.json').read_text()),
        'crosswalk': json.loads((site / 'source/diagram-crosswalk.json').read_text()),
        'model': json.loads((site / 'data/model.json').read_text()),
        'sources': json.loads((site / 'source/source-manifest.json').read_text()),
        'site': site,
    }


def main():
    report = validate_payload(**load_payload())
    report['offlineRenderer'] = validate_offline_renderer()
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
