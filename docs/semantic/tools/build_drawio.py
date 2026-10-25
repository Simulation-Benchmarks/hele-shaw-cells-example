#!/usr/bin/env python3
"""Expose the exact original draw.io XML with a separate per-cell link map.

No labels, styles, coordinates, edge directions, routing points or IDs are
reconstructed from the semantic model. The optional linked download uses the
official UserObject representation for hyperlink metadata; normalization must
recover the original XML tree exactly. Does not run the diagram renderer.
"""
from __future__ import annotations

import copy
import hashlib
import html
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'docs/semantic'
SOURCE = ROOT / 'Validation.drawio'
ONTOLOGY = 'https://nfdi4ing.pages.rwth-aachen.de/metadata4ing/metadata4ing/'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def plain(value: str) -> str:
    return re.sub(r'<[^>]*>', ' ', html.unescape(value)).strip()


def canonical_json(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def signature(element):
    """Ignore indentation only; retain all attributes, order and content."""
    return (element.tag, tuple(sorted(element.attrib.items())),
            (element.text or '').strip(), tuple(signature(c) for c in element))


def normalize_wrappers(root, value_presence):
    normalized = copy.deepcopy(root)
    for parent in normalized.iter():
        for wrapper in list(parent):
            if wrapper.tag != 'UserObject':
                continue
            assert set(wrapper.attrib) <= {'id', 'label', 'link', 'linkTarget'}
            children = list(wrapper)
            assert len(children) == 1 and children[0].tag == 'mxCell'
            cell = children[0]
            cell.set('id', wrapper.get('id'))
            if value_presence[wrapper.get('id')]:
                cell.set('value', wrapper.get('label', ''))
            position = list(parent).index(wrapper)
            parent.remove(wrapper)
            parent.insert(position, cell)
    return normalized


def main():
    source_bytes = SOURCE.read_bytes()
    source_xml = source_bytes.decode('utf-8')
    original = ET.fromstring(source_xml)
    model_bytes = (OUT/'data/model.json').read_bytes()
    crosswalk_bytes = (OUT/'source/diagram-crosswalk.json').read_bytes()
    model = json.loads(model_bytes)
    crosswalk = json.loads(crosswalk_bytes)
    assert sha(source_bytes) == crosswalk['meta']['sha256'], 'Diagram changed after semantic crosswalk build'
    assert source_bytes == (OUT/'source/Validation.drawio').read_bytes(), 'Published original is not byte-identical'
    entities = {e['id']: e for e in model['entities']}
    vertices = {v['diagramId']: v for v in crosswalk['vertices']}
    edges = {e['diagramId']: e for e in crosswalk['edges']}
    original_cells = {c.get('id'): c for c in original.findall('.//mxCell')}
    active_cells = {key: c for key,c in original_cells.items() if c.get('vertex')=='1' or c.get('edge')=='1'}
    assert len(active_cells) == len(vertices) + len(edges)
    assert set(active_cells) == set(vertices) | set(edges)
    site_url = model['meta']['namespace']
    repo_url, revision = model['meta']['repository'], model['meta']['revision']

    # Explicitly keyed by original cell ID: equal labels do not merge roles.
    source_paths = {
        'ZY6PJmolS8cB0s2s886y-38':'openfoam/Dockerfile',
        'eiFgZNk86BmHCPwQhzBy-72':'openfoam/Dockerfile',
        'TBgv5Hgd8a8wxE1-uLRW-16':'openfoam/solver/heleShawFoam.C',
        'eiFgZNk86BmHCPwQhzBy-73':'openfoam/solver/heleShawFoam.C',
        'ZY6PJmolS8cB0s2s886y-39':'openfoam/case_template/constant/transportProperties.template',
        'TBgv5Hgd8a8wxE1-uLRW-1':'openfoam/case_template/constant/transportProperties.template',
        'TBgv5Hgd8a8wxE1-uLRW-5':'openfoam/case_template/constant/transportProperties.template',
        'TBgv5Hgd8a8wxE1-uLRW-8':'openfoam/case_template/constant/transportProperties.template',
        'TBgv5Hgd8a8wxE1-uLRW-32':'openfoam/case_template/constant/turbulenceProperties.template',
        'TBgv5Hgd8a8wxE1-uLRW-33':'openfoam/case_template/constant/turbulenceProperties.template',
        'TBgv5Hgd8a8wxE1-uLRW-22':'openfoam/case_template/case2D.foam',
        'JDZ3WXQOoo0OTXsIz6hO-2':'docs/hele-shaw-cells.md',
        'JDZ3WXQOoo0OTXsIz6hO-13':'openfoam/case_template/0/U.template',
    }
    for path in sorted(set(source_paths.values())):
        subprocess.run(['git','cat-file','-e',f'{revision}:{path}'], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    notebook_base = 'notebooks/Simulation_Walkthrough.html'
    previews = {
        'ZY6PJmolS8cB0s2s886y-14':notebook_base+'#inspect-results',
        'ZY6PJmolS8cB0s2s886y-25':notebook_base+'#cartesian-figures',
        'TBgv5Hgd8a8wxE1-uLRW-24':notebook_base+'#alpha-field-inspection',
    }
    definitions = {
        'gINPJ2q_6kqyxV_ifaUd-74':ONTOLOGY+'#NumericalVariable',
        'gINPJ2q_6kqyxV_ifaUd-75':'https://qudt.org/schema/qudt/QuantityKind',
        'gINPJ2q_6kqyxV_ifaUd-76':'https://qudt.org/schema/qudt/Unit',
        'gINPJ2q_6kqyxV_ifaUd-80':ONTOLOGY+'#ProcessingStep',
        'gINPJ2q_6kqyxV_ifaUd-81':ONTOLOGY+'#Method',
        'gINPJ2q_6kqyxV_ifaUd-82':ONTOLOGY+'#Tool',
        'gINPJ2q_6kqyxV_ifaUd-84':'https://schema.org/SoftwareApplication',
        'TBgv5Hgd8a8wxE1-uLRW-14':ONTOLOGY+'#http://mlcommons.org/croissant/Field',
        'eiFgZNk86BmHCPwQhzBy-9':ONTOLOGY+'#VariableSet',
    }
    links = {}
    for cell_id, cell in active_cells.items():
        raw = cell.get('value', '')
        base = {'diagramId':cell_id, 'label':plain(raw), 'rawLabel':raw,
                'originalLabel':plain(raw), 'originalValue':raw}
        if cell_id in vertices:
            record = vertices[cell_id]
            entity = entities[record['entityId']]
            assert raw == record['originalValue']
            url = '#overview/' + quote(record['entityId'], safe='')
            link_kind, target = 'entity', '_self'
            if cell_id in source_paths:
                url = f'{repo_url}/blob/{revision}/{source_paths[cell_id]}'
                link_kind, target = 'source', '_blank'
            elif cell_id in previews:
                url, link_kind, target = previews[cell_id], 'saved-evidence', '_blank'
            elif cell_id in definitions:
                url, link_kind, target = definitions[cell_id], 'ontology-definition', '_blank'
            base.update(type='vertex', kind=entity['kind'], entityId=entity['id'],
                        normalizedLabel=record['normalizedLabel'], status=entity['status'],
                        definition=entity['definition'], url=url, target=target, linkKind=link_kind)
            if cell_id == 'eiFgZNk86BmHCPwQhzBy-7':
                base['suggestedDefinition'] = ONTOLOGY + '#Configuration'
                base['reviewNote'] = 'The original label is m4i:onfiguration. The intended Configuration term is verified, but the source spelling is preserved.'
            if cell_id in source_paths:
                base['sourcePath'] = source_paths[cell_id]
                base['sourceRevision'] = revision
            links[cell_id] = base
        else:
            record = edges[cell_id]
            assert raw == record['originalValue']
            assert cell.get('source') == record['sourceDiagramId']
            assert cell.get('target') == record['targetDiagramId']
            base.update(type='edge', kind='Relationship', entityId=None,
                        relationshipId=cell_id, relationId=record['edgeId'],
                        sourceDiagramId=cell.get('source'), targetDiagramId=cell.get('target'),
                        sourceEntityId=record['source'], targetEntityId=record['target'],
                        predicate=record['predicate'], status=record['status'],
                        reviewNote=record['reviewNote'], asserted=record['asserted'],
                        directionNormalized=record['directionNormalized'],
                        mappedSource=record['mappedSource'], mappedTarget=record['mappedTarget'],
                        normalizedLabel=record['normalizedLabel'],
                        url='#relationship/' + quote(cell_id,safe=''), target='_self', linkKind='relationship')
            links[cell_id] = base

    # Native draw.io link metadata uses UserObject wrappers. Only id/value are
    # relocated into their equivalent id/label attributes; every visual mxCell
    # attribute, child geometry, source/target and routing point is retained.
    linked = copy.deepcopy(original)
    value_presence = {cell_id: 'value' in c.attrib for cell_id,c in active_cells.items()}
    for parent in linked.iter():
        for cell in list(parent):
            cell_id = cell.get('id')
            if cell.tag != 'mxCell' or cell_id not in links:
                continue
            entry = links[cell_id]
            href = urljoin(site_url, entry['url'])
            assert urlparse(href).scheme == 'https'
            attrs = {'id':cell_id, 'link':href, 'linkTarget':entry['target']}
            if 'value' in cell.attrib:
                attrs['label'] = cell.get('value')
                del cell.attrib['value']
            del cell.attrib['id']
            wrapper = ET.Element('UserObject', attrs)
            position = list(parent).index(cell)
            parent.remove(cell)
            wrapper.append(cell)
            parent.insert(position,wrapper)
    assert signature(normalize_wrappers(linked, value_presence)) == signature(original), 'Linked derivative changed original visual or semantic cell data'
    linked_bytes = ET.tostring(linked, encoding='utf-8', xml_declaration=True) + b'\n'
    links_hash = sha(canonical_json(links))
    meta = {
        'version':1, 'sourcePath':'Validation.drawio', 'sourceDownload':'source/Validation.drawio',
        'sourceSha256':sha(source_bytes), 'sourceBytes':len(source_bytes),
        'sourceRevision':None, 'repositoryRevision':revision, 'publishedBaseUrl':site_url,
        'vertexCount':len(vertices), 'edgeCount':len(edges), 'cellCount':len(active_cells),
        'counts':{'vertices':len(vertices),'edges':len(edges),'cells':len(active_cells)},
        'crosswalkPath':'source/diagram-crosswalk.json', 'crosswalkSha256':sha(crosswalk_bytes),
        'modelPath':'data/model.json', 'modelSha256':sha(model_bytes), 'linksSha256':links_hash,
        'linkedDownload':'source/Validation.linked.drawio', 'linkedSha256':sha(linked_bytes),
        'augmentation':{
            'runtime':'Exact original XML text with an independent cell-ID hyperlink map. No original draw.io attributes or geometry changed.',
            'download':'Native UserObject link metadata; mxCell id/value are relocated losslessly to wrapper id/label. Other original attributes, child geometry, order, labels, endpoints and styles are unchanged.',
            'normalizationVerified':True, 'linksAdded':len(active_cells),
            'definitionSources':[ONTOLOGY,'https://qudt.org/schema/qudt/QuantityKind','https://qudt.org/schema/qudt/Unit','https://schema.org/SoftwareApplication'],
            'nativeFormatSource':'https://github.com/jgraph/drawio/wiki/File-Format#user-objects',
        },
    }
    payload = {'xml':source_xml, 'meta':meta, 'links':links}
    (OUT/'data').mkdir(exist_ok=True)
    (OUT/'source').mkdir(exist_ok=True)
    (OUT/'data/drawio.js').write_text('window.HELE_SHAW_DRAWIO = ' + json.dumps(payload, ensure_ascii=False,sort_keys=True,separators=(',',':')) + ';\n')
    (OUT/'source/drawio-links.json').write_bytes(canonical_json({'meta':meta,'links':links}))
    (OUT/'source/Validation.linked.drawio').write_bytes(linked_bytes)
    assert SOURCE.read_bytes() == source_bytes, 'Original source was modified'
    print(f'Prepared exact draw.io source: {len(vertices)} vertices, {len(edges)} edges, {len(links)} links; native linked derivative normalized without changes.')


if __name__ == '__main__':
    main()
