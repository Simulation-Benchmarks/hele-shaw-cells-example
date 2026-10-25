# SPDX-FileCopyrightText: 2026 Vasiliy Seibert
# SPDX-License-Identifier: MIT
"""Validate semantic structure, source evidence and the complete browser views.

This checks the representation of the research workflow. It does not run or
scientifically validate experiments, simulations, metrics or notebook cells.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

from pyshacl import validate
from rdflib import Graph, Literal, Namespace, RDF, URIRef
from rdflib.compare import isomorphic

from graph_layout import gap_label
from jupyter_service import notebook_url, setup_url

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
SVG = {'svg': 'http://www.w3.org/2000/svg'}


def read_js(path, prefix):
    text = path.read_text()
    if not text.startswith(prefix) or not text.rstrip().endswith(';'):
        raise AssertionError(f'Invalid generated browser data: {path.name}')
    return json.loads(text[len(prefix):].strip().removesuffix(';'))


def main():
    checks = []

    def check(description, condition):
        if not condition:
            raise AssertionError(description)
        checks.append(description)

    model = json.loads((HERE / 'data/model.json').read_text())
    entities = {entity['id']: entity for entity in model['entities']}
    edges = model['edges']
    graphs = read_js(HERE / 'data/graphs.js', 'window.HELE_SHAW_GRAPHS = ')
    check('Browser JSON and JavaScript projections are identical',
          read_js(HERE / 'data/model.js', 'window.HELE_SHAW = ') == model)
    check('Entity identifiers are unique and ordered deterministically',
          len(entities) == len(model['entities']) and list(entities) == sorted(entities))
    check('Every entity has a label, definition, ontology type and evidence status',
          all(entity.get('label') and entity.get('definition') and entity.get('types')
              and entity.get('status') for entity in entities.values()))
    check('All browser relationships have defined endpoints and predicate URIs',
          all(edge['source'] in entities and edge['target'] in entities
              and edge.get('predicate', '').startswith(('https://', 'http://')) for edge in edges))
    check('Relationship identifiers are unique', len({edge['id'] for edge in edges}) == len(edges))

    rdf = Graph().parse(HERE / 'model.ttl')
    hs = Namespace(model['meta']['namespace'] + 'vocabulary.ttl#')
    jsonld = Graph().parse(HERE / 'model.jsonld', format='json-ld')
    check('Turtle and JSON-LD describe isomorphic RDF graphs', isomorphic(rdf, jsonld))
    conforms, _, report = validate(rdf, shacl_graph=str(HERE / 'shapes.ttl'), inference='rdfs')
    check('SHACL application profile conforms', conforms)
    for edge in edges:
        triple = (URIRef(entities[edge['source']]['uri']), URIRef(edge['predicate']),
                  URIRef(entities[edge['target']]['uri']))
        if edge.get('asserted', True):
            if triple not in rdf:
                raise AssertionError(f'Browser assertion absent from RDF: {edge["id"]}')
        else:
            # Proposals are evidence records, never invented ontology facts.
            statement = URIRef(model['meta']['namespace'] + '#' + edge['id'])
            if not all(assertion in rdf for assertion in
                       [(statement, RDF.type, hs.RelationProposal),
                        (statement, RDF.subject, triple[0]),
                        (statement, RDF.predicate, triple[1]),
                        (statement, RDF.object, triple[2]),
                        (statement, hs.asserted, Literal(False))]):
                raise AssertionError(f'Proposed relation is not reified in RDF: {edge["id"]}')
            if triple in rdf and not any(other.get('asserted', True)
                    and (other['source'], other['predicate'], other['target'])
                    == (edge['source'], edge['predicate'], edge['target']) for other in edges):
                raise AssertionError(f'Proposal was asserted without independent evidence: {edge["id"]}')
    checks.append('Asserted browser arrows exist in RDF; proposed arrows have explicit reified evidence')

    crosswalk = json.loads((HERE / 'source/diagram-crosswalk.json').read_text())
    diagram = ET.parse(ROOT / 'Validation.drawio')
    cells = {cell.get('id'): cell for cell in diagram.iter('mxCell')}
    vertices = {key for key, cell in cells.items() if cell.get('vertex') == '1'}
    relations = {key for key, cell in cells.items() if cell.get('edge') == '1'}
    mapped_vertices = {item['diagramId']: item for item in crosswalk['vertices']}
    mapped_edges = {item['diagramId']: item for item in crosswalk['edges']}
    check('Every Validation.drawio vertex is preserved exactly once in the crosswalk',
          set(mapped_vertices) == vertices and len(mapped_vertices) == len(crosswalk['vertices']))
    check('Every Validation.drawio edge is preserved exactly once in the crosswalk',
          set(mapped_edges) == relations and len(mapped_edges) == len(crosswalk['edges']))
    for identifier, mapping in mapped_vertices.items():
        assert mapping['entityId'] in entities, identifier
        assert identifier in entities[mapping['entityId']].get('sourceDiagramIds', []), identifier
        assert mapping['originalValue'] == cells[identifier].get('value', ''), identifier
    checks.append('Crosswalk vertices retain their exact source labels and entity bindings')
    for identifier, mapping in mapped_edges.items():
        cell = cells[identifier]
        assert mapping['sourceDiagramId'] == cell.get('source'), identifier
        assert mapping['targetDiagramId'] == cell.get('target'), identifier
        assert mapping['originalValue'] == cell.get('value', ''), identifier
        assert mapping['source'] == mapped_vertices[cell.get('source')]['entityId'], identifier
        assert mapping['target'] == mapped_vertices[cell.get('target')]['entityId'], identifier
        assert any(edge['id'] == mapping['edgeId'] and edge['source'] == mapping['mappedSource']
                   and edge['target'] == mapping['mappedTarget']
                   and edge['predicate'] == mapping['predicate'] for edge in edges), identifier
        assert mapping.get('status'), identifier
        if not mapping['asserted']:
            assert mapping.get('reviewNote'), identifier
    checks.append('Crosswalk arrows retain source endpoints, labels, predicates and explicit proposal review notes')

    manifest_path = HERE / 'source/source-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    check('Source manifest hash matches the published model metadata',
          hashlib.sha256(manifest_path.read_bytes()).hexdigest() == model['meta']['sourceManifestSha256'])
    diagram_bytes = (ROOT / 'Validation.drawio').read_bytes()
    check('The source diagram is preserved byte-for-byte with its original digest',
          diagram_bytes == (HERE / 'source/Validation.drawio').read_bytes()
          and hashlib.sha256(diagram_bytes).hexdigest() == manifest['diagram']['sha256']
          == model['meta']['diagramSha256'] == crosswalk['meta']['sha256'])
    for record in manifest['files']:
        assert record['revision'] == model['meta']['revision'] == manifest['revision'], record['path']
        data = subprocess.check_output(['git', 'show', f'{record["revision"]}:{record["path"]}'], cwd=ROOT)
        assert hashlib.sha256(data).hexdigest() == record['sha256'] and len(data) == record['bytes'], record['path']
        assert record['url'] == f'{manifest["repository"]}/blob/{record["revision"]}/{record["path"]}', record['path']
    checks.append(f'All {len(manifest["files"])} source hashes and links match the pinned Git revision')
    bindings = json.loads((HERE / 'source/parameter-bindings.json').read_text())
    parameter_sources = {str(number): json.loads(subprocess.check_output(
        ['git', 'show', f'{manifest["revision"]}:parameters_{number}.json'], cwd=ROOT)) for number in (1, 2, 3)}
    for binding in bindings['bindings']:
        value = parameter_sources[binding['configuration']]
        for key in binding['selector'].split('.'):
            value = value[key]
        entity = entities[binding['bindingId']]
        assert value == binding['value'] == entity['value'], binding['bindingId']
        assert entity['selector'] == binding['selector'], binding['bindingId']
        assert any(edge['source'] == binding['bindingId']
                   and edge['target'] == f'file/parameters_{binding["configuration"]}.json'
                   and edge['predicate'].endswith('#inFile') for edge in edges), binding['bindingId']
    check('Every parameter binding resolves to its exact JSON key and value',
          len(bindings['bindings']) == len([entity for entity in entities.values() if entity['id'].startswith('binding/')]))
    repository_crosswalk = json.loads((HERE / 'source/repository-crosswalk.json').read_text())
    for mapping in repository_crosswalk['mappings']:
        assert mapped_vertices[mapping['diagramId']]['entityId'] == mapping['entityId'], mapping
        assert len(mapping['bindingIds']) == 3, mapping
        for number in (1, 2, 3):
            binding_id = f'binding/configuration-{number}/{mapping["selector"]}'
            assert binding_id in mapping['bindingIds'], mapping
            assert entities[binding_id]['selector'] == mapping['selector'], mapping
            assert any(edge['source'] == binding_id and edge['target'] == mapping['entityId']
                       and edge['predicate'].endswith('#represents') for edge in edges), mapping
    checks.append('Diagram-to-repository mappings connect each physical role to all three verified parameter configurations')

    broken_binding = Graph()
    for triple in rdf:
        broken_binding.add(triple)
    first_binding = URIRef(entities[bindings['bindings'][0]['bindingId']]['uri'])
    broken_binding.remove((first_binding, hs.inFile, None))
    negative, _, _ = validate(broken_binding, shacl_graph=str(HERE / 'shapes.ttl'), inference='rdfs')
    check('Negative test: a parameter binding without its source file fails SHACL', not negative)
    proposal = next(rdf.subjects(RDF.type, hs.RelationProposal))
    broken_proposal = Graph()
    for triple in rdf:
        broken_proposal.add(triple)
    broken_proposal.set((proposal, hs.asserted, Literal(True)))
    negative, _, _ = validate(broken_proposal, shacl_graph=str(HERE / 'shapes.ttl'), inference='rdfs')
    check('Negative test: a proposal cannot be marked as an asserted fact', not negative)

    workflow_slugs = [workflow['slug'] for workflow in model['workflows']]
    check('All four intended workflows exist with stable unique section anchors',
          workflow_slugs == ['prepare-simulate', 'inspect-results', 'check-reproducibility', 'package-share'])
    canonical = {(edge['source'], edge['target'], edge['predicate'], edge.get('id')) for edge in edges}
    for view in [model['overview'], *model['workflows']]:
        assert set(view['entities']) <= entities.keys()
        assert all((edge['source'], edge['target'], edge['predicate'], edge.get('id')) in canonical
                   for edge in view['edges'])
        assert all(edge['source'] in view['entities'] and edge['target'] in view['entities'] for edge in view['edges'])
    checks.append('Overview and workflow arrows reuse the canonical semantic relationships')
    for workflow in model['workflows']:
        assert len(workflow['stages']) == 5, workflow['slug']
        staged = [identifier for stage in workflow['stages'] for identifier in stage['entities']]
        assert len(staged) == len(set(staged)) and set(staged) == set(workflow['entities']), workflow['slug']
        assert workflow['graphKey'] == 'diagram/' + workflow['slug'], workflow['slug']
        connected = {edge[endpoint] for edge in workflow['edges'] for endpoint in ('source', 'target')}
        assert set(workflow['entities']) <= connected, f'Isolated workflow nodes: {workflow["slug"]}: {set(workflow["entities"]) - connected}'
    checks.append('Every workflow uses five stages and assigns each visible entity to exactly one stage')
    checks.append('Every visible workflow entity has a semantic connection in its diagram')
    check('All service use cases point to existing workflow sections',
          all(service.get('workflowSlugs') and set(service['workflowSlugs']) <= set(workflow_slugs)
              for service in model['services']))
    check('Each workflow has an explicit action for its service use case',
          all(workflow.get('useCaseAction') and workflow['useCaseAction'][0].islower()
              for workflow in model['workflows']))
    check('Experimental and validation evidence gaps remain explicit',
          all(gap_label(entities[identifier]) for identifier in
              ['step/experiment', 'artifact/experimental-images', 'step/experimental-postprocessing',
               'artifact/experimental-metrics', 'step/validation', 'artifact/validation-metrics']))

    expected_keys = {'overview', *entities, *(workflow['graphKey'] for workflow in model['workflows'])}
    check('Every entity has a precomputed neighborhood and all curated views exist', set(graphs) == expected_keys)
    by_index = model['entities']
    for key, graph in graphs.items():
        svg = ET.fromstring(graph['svg'])
        node_elements = [element for element in svg.iter() if element.get('class') == 'node']
        found_ids = []
        for element in node_elements:
            assert re.fullmatch(r'entity-\d+', element.get('id', '')), key
            entity = by_index[int(element.get('id').removeprefix('entity-'))]
            found_ids.append(entity['id'])
            if gap_label(entity):
                assert gap_label(entity) in ''.join(element.itertext()), (key, entity['id'])
        assert len(found_ids) == len(set(found_ids)) == graph['count'], key
        visible_edges = [element for element in svg.iter() if element.get('class') == 'edge']
        for element in visible_edges:
            assert (element.get('data-source'), element.get('data-target'),
                    element.get('data-predicate'), element.get('data-id')) in canonical, key
            assert element.get('data-source') in found_ids and element.get('data-target') in found_ids, key
        if key in entities:
            neighbors = {edge['target'] if edge['source'] == key else edge['source'] for edge in edges
                         if key in (edge['source'], edge['target'])} - {key}
            assert graph['total'] == len(neighbors) + 1 and graph['count'] <= 29, key
        else:
            view = model['overview'] if key == 'overview' else next(w for w in model['workflows'] if w['graphKey'] == key)
            assert set(found_ids) == set(view['entities']) and len(visible_edges) == len(view['edges']), key
    checks.append('Every SVG node and arrow matches its semantic view; gap text is visible and neighborhoods disclose limits')

    # Entity evidence must agree with the already verified pinned Git manifest.
    # The current README may legitimately gain site documentation after that
    # source revision; its historic source identity must remain unchanged.
    verified_paths = set()
    source_records = {record['path']: record for record in manifest['files']}
    inspection_records = {record['path']: record
                          for record in model['meta']['inspectionEvidence']['files']}
    check('The new inspection documents are distinguished from pinned scientific evidence',
          model['meta']['inspectionEvidence']['scientificSourceRevision'] == manifest['revision']
          and set(inspection_records) == {
              'docs/semantic/notebooks/inspect_results.ipynb',
              'docs/semantic/notebooks/inspect_results.py',
              'docs/semantic/notebooks/inspect_results.html',
              'docs/semantic/data/python-inspection-manifest.json'})
    for path, record in inspection_records.items():
        data = (ROOT / path).read_bytes()
        assert record['sha256'] == hashlib.sha256(data).hexdigest(), path
        assert record['bytes'] == len(data) and record['ref'] == 'main', path
        assert record['url'] == f'{manifest["repository"]}/blob/main/{path}', path
    checks.append('Current inspection documents have checksums and current-branch links')
    for entity in entities.values():
        path = entity.get('repositoryPath') or entity.get('path')
        digest = entity.get('sha256')
        if path and digest:
            if entity.get('evidenceScope') == 'current-inspection':
                assert path in inspection_records, path
                assert inspection_records[path]['sha256'] == digest, path
                assert 'revision' not in entity, path
                continue
            assert path in source_records, path
            assert source_records[path]['sha256'] == digest, path
            assert entity.get('revision') == source_records[path]['revision'], path
            verified_paths.add(path)
    if verified_paths:
        checks.append(f'{len(verified_paths)} entity file records match pinned repository evidence')

    notebook_manifest = json.loads((HERE / 'data/notebook-manifest.json').read_text())
    check('The saved notebook source is unchanged and was not executed by the site build',
          hashlib.sha256((ROOT / notebook_manifest['source']).read_bytes()).hexdigest()
          == notebook_manifest['sourceSha256']
          and notebook_manifest['verification']['executedByBuild'] is False)
    subprocess.check_output([sys.executable, str(HERE / 'tools/notebook_view.py'), '--check'])
    checks.append('Saved notebook HTML preserves all code, execution counts, tables, figures and section anchors')

    inspection = json.loads((HERE / 'data/python-inspection-manifest.json').read_text())
    check('Inspection executes only five cells over saved data, with no simulation or upload',
          inspection['revision'] == manifest['revision'] and inspection['codeCellsExecuted'] == 5
          and all(inspection[flag] is False for flag in
                  ('simulationExecuted', 'originalNotebookExecuted', 'uploadExecuted')))
    for path, expected in inspection['sources'].items():
        assert path in source_records and source_records[path]['sha256'] == expected, path
    for path, expected in inspection['outputs'].items():
        assert hashlib.sha256((HERE / path).read_bytes()).hexdigest() == expected, path
    checks.append('Inspection inputs match the pinned source manifest and every output checksum matches')
    check('The inspection preserves missing data and distinguishes original figures from the new plot',
          inspection['missingMetricEntries'] == 9 and inspection['savedImages'] == 6
          and inspection['newPlots'] == 1)
    inspection_notebook = json.loads((HERE / 'notebooks/inspect_results.ipynb').read_text())
    inspection_cells = [cell for cell in inspection_notebook['cells'] if cell['cell_type'] == 'code']
    check('All five saved inspection cells have execution counts and no error outputs',
          len(inspection_cells) == 5
          and all(type(cell.get('execution_count')) is int and cell['execution_count'] > 0
                  and not any(output.get('output_type') == 'error' for output in cell.get('outputs', []))
                  for cell in inspection_cells))
    preview_html = (HERE / 'notebooks/inspect_results.html').read_text()
    inspection_workflow = next(workflow for workflow in model['workflows'] if workflow['slug'] == 'inspect-results')
    check('The Jupyter workflow has one executable notebook section in each numbered stage',
          len(inspection['sections']) == 5
          and [section['number'] for section in inspection['sections']] == [1, 2, 3, 4, 5]
          and len(inspection_workflow['entities']) == 5)
    verified_launch = notebook_url()
    for section, stage in zip(inspection['sections'], inspection_workflow['stages']):
        number = section['number']
        identifier = f'notebook-section/inspection/stage-{number}'
        entity = entities[identifier]
        assert stage['entities'] == [identifier] and f"{number}. {stage['title']}" == section['heading'], number
        assert entity['kind'] == 'Notebook' and entity.get('navigation') != 'explore', identifier
        assert entity['sectionNumber'] == number and entity['notebookSection'] == section['anchor'], identifier
        assert entity['previewUrl'] == 'notebooks/inspect_results.html#' + section['previewAnchor'], identifier
        assert re.search(r'\bid=["\']' + re.escape(section['previewAnchor']) + r'["\']', preview_html), identifier
        assert entity.get('launchUrl') == notebook_url(section['anchor']), identifier
        assert any(source['url'].startswith(manifest['repository'] + '/blob/main/docs/semantic/notebooks/inspect_results.py#L')
                   for source in entity['sources']), identifier
        assert entities[identifier]['uri'] and 'prov:Activity' not in entity['types'], identifier
    checks.append('Each numbered inspection node opens its corresponding saved section or verified Hub heading')
    jupyter = next(service for service in model['services'] if service['id'] == 'jupyter')
    expected_status = ('Authenticated notebook launch verified' if verified_launch
                       else 'Authenticated notebook launch not yet verified')
    check('NFDI4Ing Jupyter use-case availability is gated by verified notebook evidence',
          jupyter['serviceName'] == 'NFDI4Ing Jupyter Service'
          and jupyter['workflowSlugs'] == ['inspect-results']
          and jupyter['status'] == expected_status
          and jupyter.get('launchUrl') == verified_launch
          and jupyter['setupUrl'] == setup_url()
          and entities['notebook/inspection'].get('launchUrl') == verified_launch
          and inspection_workflow.get('launchUrl') == verified_launch)
    launch_actions = [action for action in inspection_workflow['actions']
                      if action['label'] == 'Open notebook in NFDI4Ing JupyterLab']
    check('A direct notebook action is published only after verified authenticated launch',
          (len(launch_actions) == 1 and launch_actions[0]['url'] == verified_launch
           and launch_actions[0].get('sameTab') is True) if verified_launch else not launch_actions)

    result = {'conforms': True, 'checks': checks, 'triples': len(rdf),
              'entities': len(entities), 'edges': len(edges), 'graphs': len(graphs),
              'diagramVertices': len(vertices), 'diagramEdges': len(relations),
              'scope': 'Structural consistency and source evidence only. This validator executes no experiments, simulations, notebook cells, service launches or scientific validation. The separate inspection notebook records computations over saved data.',
              'shaclReport': report}
    (HERE / 'validation.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(f'Passed {len(checks)} semantic checks; {len(rdf)} triples, {len(graphs)} SVG views')


if __name__ == '__main__':
    main()
