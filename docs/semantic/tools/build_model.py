#!/usr/bin/env python3
"""Build a deterministic, evidence-linked Hele-Shaw semantic atlas.

Reads scientific sources from a pinned Git revision and the supplied draw.io
file byte-for-byte. Never executes notebooks, simulations, or external uploads.
Dependencies: rdflib. All uncertain diagram edges remain reified proposals,
not assertions of the proposed scientific relationship.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from rdflib import Graph, Literal, Namespace, RDF, RDFS, OWL, URIRef, XSD

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'docs/semantic'
REV = '8ec1b34f0a8fdbc103f35f88cba20e12b465800b'
REPO = 'https://github.com/Simulation-Benchmarks/hele-shaw-cells-example'
BASE = 'https://simulation-benchmarks.github.io/hele-shaw-cells-example/'
HS = Namespace(BASE + 'vocabulary.ttl#')
DATA = Namespace(BASE + '#')
M4I = Namespace('http://w3id.org/nfdi4ing/metadata4ing#')
PROV = Namespace('http://www.w3.org/ns/prov#')
SCHEMA = Namespace('https://schema.org/')
DCT = Namespace('http://purl.org/dc/terms/')
SH = Namespace('http://www.w3.org/ns/shacl#')
QUDT = Namespace('http://qudt.org/schema/qudt/')
g = Graph()
vocab = Graph()
for graph in (g, vocab):
    for prefix, ns in [('hs', HS), ('data', DATA), ('m4i', M4I), ('prov', PROV), ('schema', SCHEMA), ('dcterms', DCT), ('qudt', QUDT), ('owl', OWL)]:
        graph.bind(prefix, ns)
entities: dict[str, dict] = {}
edges: list[dict] = []
source_manifest: dict[str, dict] = {}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read(path: str) -> bytes:
    data = subprocess.check_output(['git', 'show', f'{REV}:{path}'], cwd=ROOT)
    source_manifest[path] = {'path': path, 'revision': REV, 'sha256': digest(data), 'bytes': len(data), 'url': source_url(path)}
    return data


def source_url(path: str) -> str:
    return f'{REPO}/blob/{REV}/{path}'


def source(path: str, label: str | None = None, target: str | None = None) -> dict:
    entry = {'url': source_url(path), 'label': label or path}
    if target:
        entry['target'] = target
    return entry


def uri(key: str) -> URIRef:
    return DATA[key]


def add(key: str, label: str, kind: str, definition: str, types=None, sources=None, status='Implemented', **extra) -> str:
    types = types or [HS[kind.replace(' ', '')]]
    entities[key] = {'id': key, 'uri': str(uri(key)), 'label': label, 'kind': kind, 'types': [g.namespace_manager.normalizeUri(t) for t in types], 'definition': definition, 'sources': sources or [], 'status': status, **extra}
    g.add((uri(key), RDF.type, HS.AtlasEntity))
    for t in types:
        g.add((uri(key), RDF.type, t))
    g.add((uri(key), RDFS.label, Literal(label)))
    g.add((uri(key), DCT.description, Literal(definition)))
    g.add((uri(key), HS.evidenceStatus, Literal(status)))
    for s in sources or []:
        target = s['url']
        g.add((uri(key), DCT.source, URIRef(target if '://' in target else BASE + target)))
    return key


def edge(a: str, predicate: URIRef, b: str, label: str, status='Mapped', source_ids=None, note=None, asserted=True) -> dict:
    assert a in entities and b in entities, (a, b)
    edge_id = 'relation/' + digest((a + '\n' + str(predicate) + '\n' + b + '\n' + ','.join(source_ids or [])).encode())[:20]
    entry = {'id': edge_id, 'source': a, 'target': b, 'predicate': str(predicate), 'label': label, 'status': status, 'asserted': asserted, 'sourceDiagramIds': source_ids or []}
    if note:
        entry['reviewNote'] = note
    if any(e['id'] == edge_id for e in edges):
        return next(e for e in edges if e['id'] == edge_id)
    edges.append(entry)
    statement = uri(edge_id)
    g.add((statement, RDF.type, RDF.Statement if asserted else HS.RelationProposal))
    g.add((statement, RDF.subject, uri(a)))
    g.add((statement, RDF.predicate, predicate))
    g.add((statement, RDF.object, uri(b)))
    g.add((statement, HS.evidenceStatus, Literal(status)))
    g.add((statement, RDFS.label, Literal(label)))
    g.add((statement, HS.asserted, Literal(asserted)))
    if asserted:
        g.add((uri(a), predicate, uri(b)))
    for cell in source_ids or []:
        g.add((statement, HS.sourceDiagramId, Literal(cell)))
    if note:
        g.add((statement, HS.reviewNote, Literal(note)))
    return entry


CLASSES = {
    'AtlasEntity': ('An entity exposed in the evidence-linked browser projection.', SCHEMA.Thing),
    'ProcessConcept': ('A named process in a conceptual workflow; does not assert a new execution.', SCHEMA.CreativeWork),
    'Model': ('The mathematical model described by the repository.', SCHEMA.CreativeWork),
    'Task': ('A scientific question or task, distinct from its execution.', SCHEMA.CreativeWork),
    'Formula': ('A mathematical expression described by the model documentation.', SCHEMA.CreativeWork),
    'Configuration': ('A configuration described by source parameters or a diagram proposal.', SCHEMA.CreativeWork),
    'VariableSet': ('A local grouping of configured variables; no unverified external class is asserted.', SCHEMA.CreativeWork),
    'NumericalVariable': ('A numerical quantity distinguished from a concrete file field.', M4I.NumericalVariable),
    'FileBinding': ('A concrete file selector corresponding to a quantity.', SCHEMA.CreativeWork),
    'Material': ('Material described in the experimental model.', SCHEMA.Thing),
    'VocabularyTerm': ('A label in the original diagram legend, retained as source evidence.', SCHEMA.DefinedTerm),
    'DiagramNote': ('A heading or annotation in the source diagram.', SCHEMA.CreativeWork),
    'Artifact': ('An expected artifact or saved file; status distinguishes available evidence from conceptual outputs.', SCHEMA.CreativeWork),
    'SavedRun': ('A historic execution documented by saved notebook outputs; not a newly executed run.', M4I.ProcessingStep),
    'RelationProposal': ('A reified relation awaiting review; its subject-predicate-object triple is not asserted.', RDF.Statement),
}
OBJECT_PROPERTIES = {
    'hasOutput': 'Relates a process concept to its expected output, without asserting execution.',
    'hasInput': 'Relates a process concept to its expected input.',
    'inputTo': 'Relates a conceptual input artifact to its consuming process; inverse of hasInput.',
    'realizesMethod': 'Relates a diagram process concept to a method; use m4i:realizesMethod for actual processing steps.',
    'usesTool': 'Relates a process concept to an employed tool.',
    'usesModel': 'Relates a simulation concept to its mathematical model.',
    'investigatesTask': 'Relates a process concept to the scientific task it investigates.',
    'hasParameter': 'Relates a conceptual model, method, tool, or configuration to a variable.',
    'configures': 'Relates a configuration to the concept being configured.',
    'hasPart': 'Relates a local conceptual grouping to a member.',
    'represents': 'Maps an implementation field or diagram occurrence to a scientific concept, without asserting identity.',
    'sourceArtifact': 'Relates a quantity or field to the artifact in which it is represented.',
    'proposedRelation': 'Unspecified source-diagram relationship retained for review.',
    'describedBy': 'Relates a scientific model to documentation.',
    'hasObservedProperty': 'Relates a dataset description to an observed property.',
    'hasConfiguredProperty': 'Relates a dataset description to a configured property.',
    'generatedByMethod': 'Relates a dataset description to a method; does not assert a completed execution.',
    'generatedBySoftware': 'Relates a dataset description to software.',
    'generatedByTool': 'Relates a dataset description to a physical tool.',
    'hasBinding': 'Relates a variable to its source-file binding.',
    'inFile': 'Relates a binding to its versioned source file.',
    'documents': 'Relates a saved artifact to the concept or execution it documents.',
    'comparesWith': 'Relates a regression process to its simulation baseline.',
    'precedes': 'Illustrated workflow order; not an execution timestamp assertion.',
    'correspondsTo': 'Crosswalk between diagram roles and repository entities.',
}
DATA_PROPERTIES = {
    'evidenceStatus': 'Evidence availability or review status, displayed in the browser.',
    'sourceDiagramId': 'Original draw.io cell or edge identifier.',
    'originalLabel': 'Unmodified plain-text spelling from the source diagram.',
    'reviewNote': 'A qualification or ambiguity requiring review.',
    'asserted': 'Whether a reified edge is also asserted as an RDF triple.',
    'sha256': 'SHA-256 digest of original source bytes.',
    'revision': 'Immutable source Git revision.',
    'path': 'Repository-relative source path.',
    'selector': 'JSON key or source selector for a binding.',
    'configuredValue': 'Literal configured value at the pinned revision.',
    'unitLabel': 'Human-readable unit copied or inferred from source documentation; not an invented QUDT URI.',
    'savedValue': 'Historic value transcribed from committed notebook output or baseline.',
}
for key, (definition, parent) in CLASSES.items():
    vocab.add((HS[key], RDF.type, OWL.Class)); vocab.add((HS[key], RDFS.label, Literal(key))); vocab.add((HS[key], RDFS.comment, Literal(definition))); vocab.add((HS[key], RDFS.subClassOf, parent))
for mapping, typ in [(OBJECT_PROPERTIES, OWL.ObjectProperty), (DATA_PROPERTIES, OWL.DatatypeProperty)]:
    for key, definition in mapping.items():
        vocab.add((HS[key], RDF.type, typ)); vocab.add((HS[key], RDFS.label, Literal(key))); vocab.add((HS[key], RDFS.comment, Literal(definition)))
vocab.add((URIRef(BASE + 'vocabulary.ttl'), RDF.type, OWL.Ontology))
vocab.add((URIRef(BASE + 'vocabulary.ttl'), RDFS.comment, Literal('Hele-Shaw application vocabulary. Diagram shorthand is preserved as evidence and mapped explicitly; the namespace is a project publication proposal.')))
vocab.add((URIRef(BASE + 'vocabulary.ttl'), DCT.source, URIRef('https://nfdi4ing.pages.rwth-aachen.de/metadata4ing/metadata4ing/')))
g += vocab
vocab.add((HS.inputTo, OWL.inverseOf, HS.hasInput))
g.add((HS.inputTo, OWL.inverseOf, HS.hasInput))

# Source inventory is immutable. The supplied, uncommitted diagram is hashed
# separately and copied without reformatting so reviewers retain the original.
paths = [
    'README.md', 'CHANGELOG.md', 'CITATION.cff', 'codemeta.json', 'LICENSE', 'PUBLISHED.md',
    'docs/hele-shaw-cells.md', 'docs/hele-shaw-cells.png', 'docs/getting_started.md', 'docs/rohub.md',
    'parameters_1.json', 'parameters_2.json', 'parameters_3.json', 'Snakefile', 'generate_config.py', 'create_mesh.py',
    'openfoam/Snakefile', 'openfoam/Dockerfile', 'openfoam/run_benchmark.py', 'openfoam/run_simulation.py',
    'openfoam/_render_templates.py', 'openfoam/solver/heleShawFoam.C', 'openfoam/solver/UEqn.H',
    'openfoam/case_template/constant/transportProperties.template', 'openfoam/case_template/constant/turbulenceProperties.template',
    'openfoam/case_template/0/U.template', 'openfoam/case_template/system/controlDict.template',
    'openfoam/metrics.py', 'openfoam/finger_pipeline.py', 'openfoam/finger_binarise.py', 'openfoam/finger_count_tips.py',
    'openfoam/plot_fingers.py', 'openfoam/ro_crate.py', 'openfoam/upload_to_rohub.py', 'openfoam/summarize_results.py',
    'tests/compare.py', 'tests/test_finger_pipeline.py', 'tests/baseline/metrics_baseline.json',
    'tests/baseline/metrics_tolerances.json', 'tests/baseline/alpha.air_t15', 'tests/baseline/log.heleShawFoam',
    'notebooks/Simulation_Walkthrough.ipynb', 'notebooks/RoCrate.ipynb', 'scripts/extract_reference_frame.py',
    '.github/workflows/run-benchmark.yml',
]
contents = {path: read(path) for path in sorted(paths)}
for path in sorted(contents):
    item = source_manifest[path]
    add('file/' + path, Path(path).name, 'File', f'Versioned repository source: {path}', [SCHEMA.MediaObject], [source(path)], 'Source', path=path, revision=REV, sha256=item['sha256'])
    for prop, value in [(HS.path, path), (HS.revision, REV), (HS.sha256, item['sha256'])]:
        g.add((uri('file/' + path), prop, Literal(value)))

diagram_bytes = (ROOT / 'Validation.drawio').read_bytes()
diagram_hash = digest(diagram_bytes)
diagram_source = {'url': 'source/Validation.drawio', 'label': 'Original Validation.drawio'}
add('source/validation-diagram', 'Validation.drawio', 'File', 'User-supplied semantic diagram, preserved byte-for-byte; not part of the pinned source revision.', [SCHEMA.MediaObject], [diagram_source], 'Source', sha256=diagram_hash)
g.add((uri('source/validation-diagram'), HS.sha256, Literal(diagram_hash)))

# One entity per original vertex, including repeated labels, legend entries,
# alternative-view occurrences, and headings. Selected nodes have readable IDs.
IDS = {
    'ZY6PJmolS8cB0s2s886y-1':'step/experiment', 'ZY6PJmolS8cB0s2s886y-3':'step/experimental-postprocessing',
    'ZY6PJmolS8cB0s2s886y-5':'step/simulation', 'ZY6PJmolS8cB0s2s886y-13':'artifact/experimental-metrics',
    'ZY6PJmolS8cB0s2s886y-14':'artifact/simulation-metrics', 'ZY6PJmolS8cB0s2s886y-18':'step/validation',
    'ZY6PJmolS8cB0s2s886y-24':'artifact/experimental-images', 'ZY6PJmolS8cB0s2s886y-25':'artifact/simulation-images',
    'ZY6PJmolS8cB0s2s886y-32':'artifact/validation-metrics', 'ZY6PJmolS8cB0s2s886y-37':'method/cfd',
    'ZY6PJmolS8cB0s2s886y-38':'software/openfoam', 'ZY6PJmolS8cB0s2s886y-39':'artifact/transport-properties',
    'gINPJ2q_6kqyxV_ifaUd-1':'step/simulation-postprocessing', 'gINPJ2q_6kqyxV_ifaUd-52':'method/comparison',
    'gINPJ2q_6kqyxV_ifaUd-55':'metric/fingers', 'gINPJ2q_6kqyxV_ifaUd-58':'metric/relative-error',
    'TBgv5Hgd8a8wxE1-uLRW-16':'software/solver', 'TBgv5Hgd8a8wxE1-uLRW-18':'task/validation',
    'TBgv5Hgd8a8wxE1-uLRW-21':'step/visualisation', 'TBgv5Hgd8a8wxE1-uLRW-22':'artifact/case-file',
    'TBgv5Hgd8a8wxE1-uLRW-24':'artifact/simulation-fields', 'TBgv5Hgd8a8wxE1-uLRW-27':'software/paraview',
    'TBgv5Hgd8a8wxE1-uLRW-41':'step/preparation', 'JDZ3WXQOoo0OTXsIz6hO-6':'model',
}
NORMALIZE = {'OpenFoam':'OpenFOAM', 'Hele Shaw Cell':'Hele-Shaw cell', 'm4i:onfiguration':'Configuration (diagram legend)', 'turbulanceProperties':'turbulenceProperties', 'exp. metrics':'Experimental metrics', 'sim. metrics':'Simulation metrics', 'exp. images':'Experimental images', 'sim. images':'Simulation images', 'validation metrics':'Validation metrics', 'testcase.foam':'OpenFOAM case file', 'hele-shaw.md':'Model documentation', 'time series data':'Simulation field time series'}
COLORS = {'#d5e8d4':('Process', HS.ProcessConcept), '#dae8fc':('Artifact', HS.Artifact), '#fff2cc':('Tool', M4I.Tool), '#ffe6cc':('Method', M4I.Method), '#d0cee2':('Software', SCHEMA.SoftwareApplication), '#f5f5f5':('Material', HS.Material), '#bac8d3':('Formula', HS.Formula), '#e1d5e7':('Binding', HS.FileBinding), '#b1ddf0':('Model', HS.Model), '#fad9d5':('Task', HS.Task), '#ffff88':('Configuration', HS.Configuration), '#f9f7ed':('Variable set', HS.VariableSet), '#008a00':('Dataset', SCHEMA.Dataset), 'none':('Note', HS.DiagramNote)}
MAPPED = {
    'step/simulation': ('Implemented', 'Simulation of radial viscous fingering using the repository runner and heleShawFoam.', ['openfoam/run_simulation.py']),
    'step/simulation-postprocessing': ('Implemented', 'Finger counts, critical radii and the interface proxy are extracted from alpha.air fields; phase fraction, continuity error and execution time are parsed from solver logs. Image processing is a separate presentation path.', ['openfoam/finger_pipeline.py', 'openfoam/metrics.py']),
    'step/visualisation': ('Implemented', 'Python renders saved fields into Cartesian plots and tip overlays. ParaView is represented in the diagram but is not required by the automated path.', ['openfoam/plot_fingers.py']),
    'step/preparation': ('Implemented', 'Prepare parameter configurations, meshes, and rendered OpenFOAM dictionaries.', ['generate_config.py', 'create_mesh.py', 'openfoam/_render_templates.py']),
    'software/openfoam': ('Implemented', 'OpenFOAM v2112 supplies the simulation framework.', ['openfoam/Dockerfile']),
    'software/solver': ('Implemented', 'The custom heleShawFoam solver is compiled in the Docker image.', ['openfoam/solver/heleShawFoam.C', 'openfoam/Dockerfile']),
    'software/paraview': ('Conceptual', 'Visualisation software named in the diagram. The current automated repository uses Python plotting.', ['openfoam/plot_fingers.py']),
    'artifact/simulation-fields': ('Saved evidence', 'Time-resolved solver fields are documented in saved notebook outputs; committed baseline alpha.air fields are also available.', ['notebooks/Simulation_Walkthrough.ipynb', 'tests/baseline/alpha.air_t15']),
    'artifact/simulation-images': ('Saved evidence', 'The saved walkthrough embeds Cartesian figures and tip overlays for three configurations.', ['notebooks/Simulation_Walkthrough.ipynb']),
    'artifact/simulation-metrics': ('Saved evidence', 'Seven scalar metric keys and a finger-count time series are produced. Three log-derived metrics are missing in the saved run.', ['notebooks/Simulation_Walkthrough.ipynb', 'openfoam/metrics.py', 'openfoam/finger_pipeline.py']),
    'artifact/transport-properties': ('Implemented', 'Rendered transportProperties binds air/soap density and viscosity, surface tension, and gap width.', ['openfoam/case_template/constant/transportProperties.template']),
    'artifact/case-file': ('Implemented', 'The diagram calls this testcase.foam; the repository template is named case2D.foam. It opens the field data in compatible software.', ['openfoam/run_simulation.py']),
    'metric/fingers': ('Saved evidence', 'final_number_of_fingers counts endpoints after alpha-field thresholding and skeletonisation. Saved configuration values are 15, 28, and 16.', ['openfoam/finger_pipeline.py', 'notebooks/Simulation_Walkthrough.ipynb']),
    'metric/relative-error': ('Proposed', 'An experiment-versus-simulation relative error belongs to the conceptual validation model. No such result is supplied in this repository.', []),
    'step/validation': ('Proposed', 'Compare experimental and simulation metrics. Actual experimental observations and a matched comparison are not included.', []),
    'artifact/validation-metrics': ('Proposed', 'Expected validation output; no experimentally grounded relative-error values are supplied.', []),
    'model': ('Documented', 'Mathematical description of the air–soap flow and its implementation in heleShawFoam. This atlas links the existing specification without revalidating its equations.', ['docs/hele-shaw-cells.md', 'openfoam/solver/heleShawFoam.C']),
    'task/validation': ('Conceptual', 'Compare the radial fingering behaviour of a physical Hele-Shaw experiment and a CFD model.', []),
}
root = ET.fromstring(diagram_bytes)
cells = root.findall('.//mxCell')
vertices, diagram_edges = [], []
by_diagram = {}
for c in cells:
    if c.get('vertex') != '1':
        continue
    original = re.sub(r'<[^>]*>', ' ', html.unescape(c.get('value', ''))).strip()
    label = NORMALIZE.get(original, original)
    cid = c.get('id')
    key = IDS.get(cid, 'diagram-cell/' + cid)
    style = c.get('style', '')
    color = re.search(r'(?:^|;)fillColor=([^;]+)', style)
    kind, typ = COLORS.get(color.group(1) if color else '', ('Variable', M4I.NumericalVariable))
    is_legend = original.startswith(('m4i:', 'qudt:', 'schema:', 'ontoMS:', 'cr:'))
    if is_legend:
        kind, typ = 'Vocabulary', HS.VocabularyTerm
    elif original == 'Model':
        kind, typ = 'Model', HS.Model
    role = 'primary-process-model'
    if cid.startswith('eiFgZN'):
        role = 'dataset-oriented-view' if int(cid.rsplit('-', 1)[1]) >= 38 else 'configuration-view'
    if is_legend:
        role = 'legend'
    if original == 'Post-Processing':
        label = 'Experimental post-processing' if key.endswith('experimental-postprocessing') else 'Simulation post-processing'
    if key == 'step/preparation':
        label = 'Preparation'
    status, definition, evidence_paths = MAPPED.get(key, ('Conceptual', f'{label} in the {role.replace("-", " ")} of Validation.drawio. This occurrence retains its own identity and does not establish an executed experiment.', []))
    if is_legend:
        status, definition = 'Source', f'Original diagram legend label “{original}”. This is a source annotation, not an assertion that the shorthand is a valid external ontology term.'
    if kind == 'Note':
        status = 'Source'
    sources = [source(p) for p in evidence_paths] + [diagram_source]
    add(key, label, kind, definition, [typ], sources, status, sourceDiagramIds=[cid], originalLabel=original, diagramRole=role)
    if kind == 'Software':
        g.add((uri(key), RDF.type, M4I.Tool))
        entities[key]['types'].append('m4i:Tool')
    g.add((uri(key), HS.sourceDiagramId, Literal(cid)))
    g.add((uri(key), HS.originalLabel, Literal(original)))
    by_diagram[cid] = key
    vertices.append({'diagramId': cid, 'entityId': key, 'originalValue': c.get('value', ''), 'originalLabel': original, 'normalizedLabel': label, 'role': role, 'kind': kind, 'status': status, 'style': style, 'geometry': c.find('mxGeometry').attrib if c.find('mxGeometry') is not None else {}})

# No guessed ontology terms. Unlabelled or question-mark relations are retained
# as proposals, including their original direction. Direction mistakes are not
# silently corrected in source evidence.
RELATIONS = {
    'has output':(HS.hasOutput, False), 'is input of':(HS.inputTo, False), 'input of':(HS.inputTo, False),
    'realizes method':(HS.realizesMethod, False), 'investigates':(HS.investigatesTask, False), 'uses':(HS.usesModel, False),
    'implemented by':(M4I.implementedByTool, False), 'softwareRequirements':(SCHEMA.softwareRequirements, False),
    'has parameter':(HS.hasParameter, False), 'source':(HS.sourceArtifact, False), 'has part':(HS.hasPart, False),
    'has kind of quantity':(M4I.hasKindOfQuantity, False), 'has measurement unit':(M4I.hasUnit, False),
    'represents':(HS.represents, False), 'described by':(HS.describedBy, False), 'has employed tool':(HS.usesTool, False),
    'configures':(HS.configures, False), 'part of':(HS.hasPart, True), 'contains':(HS.hasPart, False),
    'includes observed property':(HS.hasObservedProperty, False), 'includes configured property':(HS.hasConfiguredProperty, False),
    'was generated by method':(HS.generatedByMethod, False), 'was generated by software':(HS.generatedBySoftware, False), 'was generated by tool':(HS.generatedByTool, False),
}
CORE_PROPOSALS = {
    ('artifact/experimental-images','step/experimental-postprocessing'):(HS.inputTo,'input to'),
    ('step/experimental-postprocessing','artifact/experimental-metrics'):(HS.hasOutput,'has output'),
    ('artifact/experimental-metrics','step/validation'):(HS.inputTo,'input to'),
    ('step/simulation-postprocessing','artifact/simulation-metrics'):(HS.hasOutput,'has output'),
    ('artifact/simulation-images','step/simulation-postprocessing'):(HS.inputTo,'input to'),
}
for c in cells:
    if c.get('edge') != '1':
        continue
    cid, s, t = c.get('id'), c.get('source'), c.get('target')
    original = re.sub(r'<[^>]*>', ' ', html.unescape(c.get('value', ''))).strip()
    predicate, reverse = RELATIONS.get(original, (HS.proposedRelation, False))
    uncertain = not original or '?' in original or original not in RELATIONS
    note = 'Unlabelled diagram edge; relation requires review.' if not original else ('Diagram relation is explicitly uncertain; preserved without asserting it.' if '?' in original else None)
    if s == 'gINPJ2q_6kqyxV_ifaUd-64' and t == 'gINPJ2q_6kqyxV_ifaUd-52':
        uncertain = True; note = 'Original direction is Validation code → comparison, labelled implemented by. Expected method/tool direction needs review; original direction is preserved.'
    if any(entities.get(by_diagram.get(x), {}).get('kind') == 'Vocabulary' for x in (s, t)):
        uncertain = True; note = 'Diagram legend connection is explanatory source evidence, not a relation between actual quantity/unit individuals.'
    source_id, target_id = by_diagram.get(s), by_diagram.get(t)
    proposed_label = None
    if not original and (source_id,target_id) in CORE_PROPOSALS:
        predicate, proposed_label = CORE_PROPOSALS[(source_id,target_id)]
        note = 'Unlabelled core diagram edge. This specific relation is a review proposal based on the surrounding input/output flow; the source did not name a predicate.'
    a, b = (target_id, source_id) if reverse and not uncertain else (source_id, target_id)
    status = 'Proposed' if uncertain else 'Diagram mapping'
    e = None
    if a and b:
        display_label = 'has part' if reverse and not uncertain else proposed_label or original or 'relation to review'
        e = edge(a, predicate, b, display_label, status, [cid], note, not uncertain)
    diagram_edges.append({'diagramId': cid, 'sourceDiagramId': s, 'targetDiagramId': t, 'source': source_id, 'target': target_id, 'mappedSource': a, 'mappedTarget': b, 'originalValue': c.get('value', ''), 'originalLabel': original, 'normalizedLabel': display_label if e else original or 'relation to review', 'predicate': str(predicate), 'status': status, 'asserted': not uncertain and bool(a and b), 'directionNormalized': bool(reverse and not uncertain), 'reviewNote': note, 'edgeId': e['id'] if e else None, 'style': c.get('style', '')})

# Repository-specific extension, carefully separated from the conceptual model.
add('repository', 'Hele-Shaw cells example', 'Repository', 'Pinned source repository for the implemented simulation and saved evidence.', [SCHEMA.SoftwareSourceCode], [{'label':'Repository', 'url':REPO}], 'Source', revision=REV)
add('notebook/walkthrough', 'Saved simulation walkthrough', 'Notebook', 'The committed notebook contains saved output for three configurations, figures, metrics, regression checks and a local RO-Crate inspection. It is rendered without executing code.', [SCHEMA.DigitalDocument], [source('notebooks/Simulation_Walkthrough.ipynb')], 'Saved evidence', previewUrl='notebooks/Simulation_Walkthrough.html')
add('artifact/saved-run', 'Saved three-configuration run', 'Run', 'Historic run documented in the notebook. Three log-derived metrics are missing; configuration 1 passes the available baseline checks, while changed configurations differ from that reference.', [HS.SavedRun, M4I.ProcessingStep, PROV.Activity], [source('notebooks/Simulation_Walkthrough.ipynb')], 'Saved evidence')
edge('artifact/saved-run', M4I.realizesMethod, 'method/cfd', 'realizes CFD', 'Saved evidence')
edge('artifact/saved-run', M4I.hasEmployedTool, 'software/solver', 'employed solver', 'Saved evidence')
edge('notebook/walkthrough', HS.documents, 'artifact/saved-run', 'documents', 'Saved evidence')
add('software/python-postprocessing', 'Python post-processing', 'Software', 'Repository scripts extract metrics and render figures from existing solver fields.', [SCHEMA.SoftwareApplication, M4I.Tool], [source('openfoam/finger_pipeline.py'), source('openfoam/plot_fingers.py')])
add('artifact/mesh', 'Generated mesh', 'Artifact', 'The mesh is generated from a parameter configuration and supplied to the solver; generated mesh archives are not committed evidence.', [HS.Artifact], [source('create_mesh.py')], 'Implemented')
add('artifact/rendered-case', 'Rendered OpenFOAM case', 'Artifact', 'Jinja2 templates bind parameter JSON to OpenFOAM dictionaries.', [HS.Artifact], [source('openfoam/_render_templates.py')])
add('artifact/time-series', 'Finger count over time', 'Artifact', 'n_fingers_over_time maps saved simulation times to field-based fingertip counts. Curves for all three configurations are embedded in the saved notebook.', [HS.Artifact], [source('openfoam/finger_pipeline.py'), source('notebooks/Simulation_Walkthrough.ipynb')], 'Saved evidence', previewUrl='notebooks/Simulation_Walkthrough.html#finger-metrics')
add('metric/radius', 'Critical radius', 'Variable', 'critical_radius_m is the minimum distance from the centre to the binarised air-region boundary, in metres.', [M4I.NumericalVariable], [source('openfoam/finger_pipeline.py')], 'Saved evidence')
add('artifact/baseline', 'Committed simulation baseline', 'Artifact', 'Configuration 1 reference alpha fields, log, metric values and tolerances. This is simulation-regression evidence, not an experimental observation.', [HS.Artifact], [source('tests/baseline/metrics_baseline.json'), source('tests/baseline/metrics_tolerances.json')], 'Source')
add('step/regression', 'Baseline regression check', 'Process', 'Compare fresh or saved simulation metrics/fields with the configuration 1 baseline; missing metric values are skipped.', [HS.ProcessConcept], [source('tests/compare.py')])
add('artifact/regression-report', 'Saved regression results', 'Artifact', 'Saved notebook: configuration 1 has 4 passes and 3 skips. Configuration 2 has 2 failures; configuration 3 has 1 failure against the configuration 1 baseline. Changed configurations are sensitivity cases.', [HS.Artifact], [source('notebooks/Simulation_Walkthrough.ipynb')], 'Saved evidence', previewUrl='notebooks/Simulation_Walkthrough.html#regression-checks')
add('step/package', 'Package provenance', 'Process', 'The repository packages parameters, outputs, software and a local RO-Crate metadata graph. Its current writer has a simpler model than the conceptual diagram.', [HS.ProcessConcept], [source('openfoam/ro_crate.py'), source('openfoam/run_simulation.py')])
add('artifact/ro-crate', 'RO-Crate package', 'Dataset', 'A saved notebook inspects the local m4i-augmented package. The existing writer describes one run as m4i:Method and uses schema:PropertyValue; this atlas does not silently rewrite those source claims.', [SCHEMA.Dataset], [source('openfoam/ro_crate.py'), source('notebooks/Simulation_Walkthrough.ipynb')], 'Saved evidence', previewUrl='notebooks/Simulation_Walkthrough.html#ro-crate-inspection')
add('step/rohub-upload', 'Optional ROHub upload', 'Process', 'An upload script is available, but no successful upload UUID is recorded in this checkout. No upload is performed by the site.', [HS.ProcessConcept], [source('openfoam/upload_to_rohub.py'), source('docs/rohub.md')], 'Optional; upload unverified')
add('artifact/rohub-query', 'ROHub query guide', 'Artifact', 'SPARQL examples explain how an uploaded research object could be queried. The saved ROHub notebook is unexecuted and is not evidence of publication.', [SCHEMA.DigitalDocument], [source('docs/rohub.md')], 'Optional; upload unverified')
add('artifact/reference-image', 'Reference simulation image', 'Artifact', 'Historical simulation frame at approximately 10 s, according to the extraction script. The original AVI is not included in this checkout.', [SCHEMA.ImageObject], [source('docs/hele-shaw-cells.png'), source('scripts/extract_reference_frame.py')], 'Saved evidence', previewUrl='notebooks/assets/hele-shaw-cells.png')

parameter_records = []
for n in (1, 2, 3):
    path = f'parameters_{n}.json'
    params = json.loads(contents[path])
    names = {1:'Reference configuration', 2:'Mesh refinement', 3:'Double injection rate'}
    definition = f'Configuration {n}: NPA={params["mesh"]["NPA"]}, NPZ={params["mesh"]["NPZ"]}, inlet flow rate={params["boundary_conditions"]["inlet_volumetric_flow_rate"]:g} m³/s; end time={params["solver"]["endTime"]:g} s.'
    add(f'configuration/{n}', names[n], 'Configuration', definition, [HS.Configuration], [source(path)], 'Source', navigation='explore')
    edge('step/preparation', HS.hasInput, f'configuration/{n}', 'uses configuration', 'Source')
    edge(f'configuration/{n}', HS.sourceArtifact, 'file/' + path, 'stored in', 'Source')
    def flatten(d, prefix=''):
        for k, value in sorted(d.items()):
            selector = prefix + k
            if isinstance(value, dict):
                yield from flatten(value, selector + '.')
            else:
                yield selector, value
    for selector, value in flatten(params):
        if selector == 'configuration':
            continue
        key = f'binding/configuration-{n}/{selector}'
        add(key, f'{selector} · config {n}', 'Binding', f'{selector} = {value} in {path}.', [HS.FileBinding], [source(path)], 'Source', selector=selector, value=value)
        g.add((uri(key), HS.selector, Literal(selector))); g.add((uri(key), HS.configuredValue, Literal(value)))
        edge(key, HS.inFile, 'file/' + path, 'in file', 'Source')
        edge(f'configuration/{n}', HS.hasBinding, key, 'has binding', 'Source')
        parameter_records.append({'configuration': str(n), 'selector': selector, 'value': value, 'bindingId': key})

# Explicit source-to-concept correspondences connect the diagram to real JSON
# selectors without merging the distinct diagram occurrences or asserting that
# experimental apparatus was configured or operated.
quantity_mapping = [
    ('gINPJ2q_6kqyxV_ifaUd-8','boundary_conditions.inlet_volumetric_flow_rate','m³/s'),
    ('gINPJ2q_6kqyxV_ifaUd-26','domain.R_in','m'),
    ('gINPJ2q_6kqyxV_ifaUd-30','domain.b','m'),
    ('gINPJ2q_6kqyxV_ifaUd-33','fluids.air.rho','kg/m³'),
    ('gINPJ2q_6kqyxV_ifaUd-34','fluids.air.k','m²/s (Newtonian n = 1)'),
    ('ZY6PJmolS8cB0s2s886y-47','fluids.soap.rho','kg/m³'),
    ('gINPJ2q_6kqyxV_ifaUd-12','fluids.soap.k','m²/s (Newtonian n = 1)'),
    ('gINPJ2q_6kqyxV_ifaUd-15','fluids.sigma','N/m'),
    ('TBgv5Hgd8a8wxE1-uLRW-1','fluids.air.rho','kg/m³'),
    ('TBgv5Hgd8a8wxE1-uLRW-5','fluids.soap.rho','kg/m³'),
    ('TBgv5Hgd8a8wxE1-uLRW-8','fluids.sigma','N/m'),
    ('JDZ3WXQOoo0OTXsIz6hO-13','boundary_conditions.inlet_volumetric_flow_rate','m³/s'),
]
repository_crosswalk = []
for diagram_id, selector, unit in quantity_mapping:
    entity_id = by_diagram[diagram_id]
    entities[entity_id]['unitLabel'] = unit
    entities[entity_id]['sources'].append(source('parameters_1.json'))
    g.add((uri(entity_id), DCT.source, URIRef(source_url('parameters_1.json'))))
    g.add((uri(entity_id), HS.unitLabel, Literal(unit)))
    ids = []
    for n in (1,2,3):
        binding_id = f'binding/configuration-{n}/{selector}'
        edge(binding_id, HS.represents, entity_id, 'maps to diagram quantity', 'Repository mapping')
        ids.append(binding_id)
    repository_crosswalk.append({'diagramId':diagram_id,'entityId':entity_id,'selector':selector,'unitLabel':unit,'bindingIds':ids,'status':'Repository mapping','note':'Correspondence to a simulation input; does not assert a configured experimental execution.'})

PIPELINE = [
    ('step/preparation', HS.hasOutput, 'artifact/mesh', 'generates mesh'),
    ('step/preparation', HS.hasOutput, 'artifact/rendered-case', 'renders case'),
    ('step/simulation', HS.hasInput, 'artifact/mesh', 'uses mesh'),
    ('step/simulation', HS.hasInput, 'artifact/rendered-case', 'uses case'),
    ('step/simulation', HS.hasOutput, 'artifact/simulation-fields', 'writes fields'),
    ('step/simulation', HS.usesTool, 'software/solver', 'uses solver'),
    ('step/simulation', HS.usesModel, 'model', 'implements model'),
    ('step/simulation-postprocessing', HS.hasInput, 'artifact/simulation-fields', 'reads alpha fields'),
    ('step/simulation-postprocessing', HS.usesTool, 'software/python-postprocessing', 'uses Python scripts'),
    ('step/simulation-postprocessing', HS.hasOutput, 'artifact/simulation-metrics', 'extracts metrics'),
    ('step/simulation-postprocessing', HS.hasOutput, 'artifact/time-series', 'extracts time series'),
    ('artifact/simulation-metrics', HS.hasPart, 'metric/fingers', 'includes finger count'),
    ('artifact/simulation-metrics', HS.hasPart, 'metric/radius', 'includes critical radius'),
    ('step/visualisation', HS.hasInput, 'artifact/simulation-fields', 'renders fields'),
    ('step/visualisation', HS.usesTool, 'software/python-postprocessing', 'uses Python plotting'),
    ('step/visualisation', HS.hasOutput, 'artifact/simulation-images', 'renders figures'),
    ('step/regression', HS.hasInput, 'artifact/simulation-metrics', 'checks metrics'),
    ('step/regression', HS.comparesWith, 'artifact/baseline', 'compares with baseline'),
    ('step/regression', HS.hasOutput, 'artifact/regression-report', 'reports differences'),
    ('step/package', HS.hasInput, 'artifact/simulation-fields', 'packages fields'),
    ('step/package', HS.hasInput, 'artifact/simulation-metrics', 'packages metrics'),
    ('step/package', HS.hasInput, 'configuration/1', 'packages parameters'),
    ('step/package', HS.hasOutput, 'artifact/ro-crate', 'writes RO-Crate'),
    ('step/rohub-upload', HS.hasInput, 'artifact/ro-crate', 'accepts package'),
    ('step/rohub-upload', HS.hasOutput, 'artifact/rohub-query', 'enables queries after upload'),
    ('notebook/walkthrough', HS.documents, 'artifact/simulation-images', 'contains saved figures'),
    ('notebook/walkthrough', HS.documents, 'artifact/regression-report', 'contains saved checks'),
    ('notebook/walkthrough', HS.documents, 'artifact/reference-image', 'includes reference image'),
    ('notebook/walkthrough', HS.documents, 'artifact/ro-crate', 'contains metadata inspection'),
    ('artifact/baseline', HS.documents, 'configuration/1', 'reference for configuration'),
    ('artifact/saved-run', HS.hasOutput, 'artifact/simulation-metrics', 'saved metric evidence'),
]
for a, p, b, label in PIPELINE:
    status = 'Optional; upload unverified' if a == 'step/rohub-upload' else 'Repository mapping'
    edge(a, p, b, label, status)

# Clarify image-based conceptual processing versus the implemented field path.
edge('step/simulation-postprocessing', HS.hasInput, 'artifact/simulation-images', 'conceptual image input', 'Proposed', note='The diagram connects simulation images to processing. Production finger/interface metrics use alpha.air directly; other metrics come from solver logs.', asserted=False)

def stage(key, title, summary, ids):
    return {'id':key, 'title':title, 'summary':summary, 'entities':ids}


def curated_edges(ids):
    selected = set(ids)
    priority = {'Repository mapping':0, 'Saved evidence':0, 'Source':0, 'Diagram mapping':1, 'Mapped':1, 'Conceptual':2, 'Proposed':3}
    candidates = [e for e in edges if e['source'] in selected and e['target'] in selected and e['predicate'] != str(HS.proposedRelation)]
    chosen = {}
    for e in sorted(candidates, key=lambda e:(priority.get(e['status'],2), e['id'])):
        chosen.setdefault((e['source'],e['predicate'],e['target']),e)
    # Prefer the source diagram's input-to direction when its inverse is also present.
    inverse_pairs = {(e['target'], str(HS.hasInput), e['source']) for e in chosen.values() if e['predicate'] == str(HS.inputTo)}
    return [e for key, e in chosen.items() if key not in inverse_pairs]


def workflow(slug, title, summary, caveat, stages, anchor, actions=None):
    ids = [i for s in stages for i in s['entities']]
    assert len(ids) == len(set(ids)), slug
    selected = set(ids)
    view_edges = curated_edges(ids)
    if slug == 'inspect-results':
        # This concrete workflow follows field/log processing. The image-input
        # proposal stays visible in the semantic overview and full RDF.
        view_edges = [e for e in view_edges if not (
            {e['source'], e['target']} == {'step/simulation-postprocessing', 'artifact/simulation-images'}
            or (e['source'] == 'metric/fingers' and e['target'] == 'artifact/simulation-metrics'))]
    return {'slug':slug, 'graphKey':'diagram/' + slug, 'title':title, 'summary':summary, 'caveat':caveat, 'stages':stages, 'entities':ids, 'edges':view_edges, 'actions':actions or [{'label':'Read saved walkthrough', 'url':'notebooks/Simulation_Walkthrough.html#' + anchor}, {'label':'View source notebook', 'url':source_url('notebooks/Simulation_Walkthrough.ipynb')}], 'previewUrl':'notebooks/Simulation_Walkthrough.html#' + anchor}

workflows = [
    workflow('prepare-simulate', 'Prepare and simulate', 'Follow three parameter configurations into meshes, OpenFOAM cases, and solver fields.', 'The site presents source and saved-run evidence; it does not execute the solver.', [
        stage('configure','Choose parameters','Reference, refined mesh, or doubled flow rate.',['configuration/1','configuration/2','configuration/3']),
        stage('prepare','Prepare the case','Generate meshes and bind templates.',['step/preparation','artifact/mesh','artifact/rendered-case']),
        stage('model','Use the model','Connect equations to the OpenFOAM implementation.',['model','software/openfoam','software/solver']),
        stage('simulate','Run the simulation','The runner invokes the custom solver.',['step/simulation']),
        stage('fields','Inspect field output','Saved notebook evidence records the produced fields.',['artifact/simulation-fields','artifact/saved-run']),
    ], 'run-simulation'),
    workflow('inspect-results', 'Inspect results', 'Trace finger counts and critical radii to alpha fields, then inspect saved figures and time series.', 'Finger counts, critical radii and the interface proxy use alpha fields; phase fraction, continuity error and execution time come from solver logs. PNG-based tip overlays are a separate visualisation path.', [
        stage('fields','Start with fields','Use saved alpha.air output.',['artifact/simulation-fields']),
        stage('extract','Extract metrics','Threshold, skeletonise and count field-based tips.',['step/simulation-postprocessing','software/python-postprocessing']),
        stage('measure','Read measurements','Inspect counts, radii and the time series.',['artifact/simulation-metrics','metric/fingers','metric/radius','artifact/time-series']),
        stage('render','Render figures','Visualise the field independently of metric extraction.',['step/visualisation','artifact/simulation-images']),
        stage('notebook','Open saved evidence','Read embedded outputs without executing the notebook.',['notebook/walkthrough','artifact/reference-image']),
    ], 'inspect-results'),
    workflow('check-reproducibility', 'Check reproducibility', 'Compare simulation results with the committed reference and inspect the saved pass, fail, and skip outcomes.', 'Regression against a simulation baseline is not experiment-versus-simulation validation. Changed configurations are sensitivity cases.', [
        stage('reference','Select the reference','Configuration 1 is the regression reference.',['configuration/1','artifact/baseline']),
        stage('results','Choose result evidence','Use saved metrics or outputs from a separate fresh run.',['artifact/simulation-metrics','artifact/saved-run']),
        stage('compare','Compare with tolerances','The comparison script skips missing values.',['step/regression']),
        stage('report','Review outcomes','Saved output includes passes, skips and sensitivity differences.',['artifact/regression-report']),
        stage('boundary','Keep validation distinct','Experimental comparison remains a proposed extension.',['step/validation','artifact/validation-metrics']),
    ], 'regression-checks'),
    workflow('package-share', 'Package and share', 'Follow inputs and outputs into a local RO-Crate, then explore the optional ROHub publication route.', 'Local packaging is evidenced in the notebook. No successful ROHub upload or project-specific JupyterHub launch is verified.', [
        stage('collect','Collect evidence','Bundle parameters and simulation outputs.',['configuration/1','artifact/simulation-fields','artifact/simulation-metrics']),
        stage('package','Describe provenance','The current writer creates its documented RO-Crate profile.',['step/package']),
        stage('crate','Inspect the package','A saved notebook cell inspects local metadata.',['artifact/ro-crate','notebook/walkthrough']),
        stage('upload','Upload optionally','The upload script requires a separate configured account.',['step/rohub-upload']),
        stage('query','Explore query guidance','Use the guide after a successful upload.',['artifact/rohub-query']),
    ], 'ro-crate-inspection', [{'label':'Inspect saved RO-Crate output','url':'notebooks/Simulation_Walkthrough.html#ro-crate-inspection'}, {'label':'Read ROHub guide','url':source_url('docs/rohub.md')}]),
]

overview_groups = [
    {'id':'model','title':'Model and configuration','entities':['model','configuration/1','configuration/2','configuration/3']},
    {'id':'experiment','title':'Experimental branch · conceptual','entities':['step/experiment','artifact/experimental-images','step/experimental-postprocessing','artifact/experimental-metrics']},
    {'id':'simulation','title':'Simulation branch · implemented','entities':['step/preparation','step/simulation','artifact/simulation-fields','step/simulation-postprocessing','artifact/simulation-metrics']},
    {'id':'validation','title':'Comparison · proposed','entities':['step/validation','artifact/validation-metrics']},
    {'id':'imaging','title':'Visualisation and image-processing path','entities':['step/visualisation','artifact/simulation-images']},
]
overview_ids = [i for group in overview_groups for i in group['entities']]
overview_set = set(overview_ids)
overview = {'entities':overview_ids, 'edges':curated_edges(overview_ids), 'groups':overview_groups, 'summary':'Experiment and simulation meet at validation. Conceptual steps and proposed links are labeled.'}

services = [
    {'id':'mvp', 'name':'Model Validation Platform', 'serviceName':'NFDI4Ing Model Validation Platform', 'url':'https://github.com/Simulation-Benchmarks/NFDI4IngModelValidationPlatform', 'workflowSlugs':['prepare-simulate','check-reproducibility'], 'logos':[], 'status':'Repository integration documented', 'summary':'The example follows the platform instance-repository layout and benchmark contract; registration is documented by the repository.'},
    {'id':'jupyter', 'name':'NFDI4Ing Jupyter Hub', 'serviceName':'NFDI4Ing Jupyter Hub', 'url':'https://jupyter.nfdi4ing.de/', 'workflowSlugs':['inspect-results'], 'logos':[], 'status':'Project launch not configured', 'summary':'Use the saved notebook view now, or follow the installation guide for a local environment. No project-specific hosted launch URL is configured.', 'previewUrl':'notebooks/Simulation_Walkthrough.html'},
    {'id':'rohub', 'name':'ROHub', 'serviceName':'ROHub', 'url':'https://www.rohub.org/', 'workflowSlugs':['package-share'], 'logos':[], 'status':'Optional; upload unverified', 'summary':'Upload and query scripts are supplied. No successful upload identifier is recorded in the inspected sources.'},
]

crosswalk = {'meta':{'source':'Validation.drawio','sha256':diagram_hash,'vertexCount':len(vertices),'edgeCount':len(diagram_edges),'policy':'Every original vertex and edge is retained. Duplicate labels keep distinct entity identities. Unlabelled, uncertain, and direction-conflicted edges are proposals, not asserted domain triples.'}, 'vertices':vertices, 'edges':diagram_edges}
manifest = {'revision':REV, 'repository':REPO, 'diagram':{'path':'Validation.drawio','sha256':diagram_hash,'bytes':len(diagram_bytes),'revision':None}, 'files':[source_manifest[p] for p in sorted(source_manifest)]}
manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode()
metrics = ['phase1_volume_fraction','cumulative_continuity_error','interface_length_proxy','wall_time_seconds','time_step_count','final_number_of_fingers','critical_radius_m']
for item in entities.values():
    if item['kind'] in {'Process','Variable','Model','Task','Formula','Method','Configuration','Variable set','Binding','Material','Run'}:
        item['navigation'] = 'explore'
    # Repository evidence is the primary source action; original diagram
    # evidence remains available in the semantic dataset as a secondary source.
    item['sources'].sort(key=lambda s: 0 if s['url'].startswith(REPO + '/blob/') else 1)
    if item['id'] != 'source/validation-diagram' and item['sources'] and all(s['url'] == 'source/Validation.drawio' for s in item['sources']):
        item['navigation'] = 'explore'
model = {
    'meta': {'title':'Hele-Shaw semantic atlas', 'revision':REV, 'repository':REPO, 'namespace':BASE, 'ontology':'Metadata4Ing + PROV-O + schema.org + explicit Hele-Shaw extensions', 'version':'1.0.0-review', 'scope':'Source-backed simulation workflows aligned with the complete Validation.drawio crosswalk; experimental acquisition and scientific validation remain conceptual.', 'triples':len(g), 'fileCount':len(source_manifest)+1, 'variableCount':sum(e['kind']=='Variable' for e in entities.values()), 'diagramSha256':diagram_hash, 'sourceManifestSha256':digest(manifest_bytes), 'diagramVertexCount':len(vertices), 'diagramEdgeCount':len(diagram_edges), 'metricNames':metrics, 'seriesNames':['n_fingers_over_time'], 'evidenceNote':'Saved notebook output is historic evidence, not a new execution. Experimental observations and completed ROHub uploads are not supplied.'},
    'entities':[entities[k] for k in sorted(entities)], 'edges':sorted(edges, key=lambda e:e['id']), 'overview':overview, 'workflows':workflows, 'services':services,
}


def stable_turtle(graph):
    # Full-IRI, one-triple-per-line Turtle is deterministic and also valid N-Triples.
    return '\n'.join(sorted(f'{s.n3()} {p.n3()} {o.n3()} .' for s,p,o in graph)) + '\n'


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n')


def main():
    for folder in ['source','data']:
        (OUT/folder).mkdir(parents=True, exist_ok=True)
    (OUT/'source/Validation.drawio').write_bytes(diagram_bytes)
    (OUT/'source/source-manifest.json').write_bytes(manifest_bytes)
    write_json(OUT/'source/diagram-crosswalk.json', crosswalk)
    write_json(OUT/'source/parameter-bindings.json', {'revision':REV, 'bindings':parameter_records})
    write_json(OUT/'source/repository-crosswalk.json', {'revision':REV, 'mappings':repository_crosswalk})
    write_json(OUT/'source/ontology-term-audit.json', {
        'metadata4ing': {'namespace':str(M4I), 'version':'1.4.0', 'source':'https://nfdi4ing.pages.rwth-aachen.de/metadata4ing/metadata4ing/', 'terms':['NumericalVariable','Method','Tool','ProcessingStep','realizesMethod','hasEmployedTool','implementedByTool','hasKindOfQuantity','hasUnit']},
        'prov': {'namespace':str(PROV), 'source':'https://www.w3.org/TR/prov-o/', 'terms':['Activity']},
        'diagramOnlyLabels':['schema:FileObject','ontoMS:Model','ontoMS:Task','m4i:VariableSet','m4i:onfiguration','cr:Field'],
        'policy':'Diagram-only labels are source vocabulary annotations, not asserted external classes. Local hs:ProcessConcept and hs relations distinguish conceptual workflows from the historic m4i:ProcessingStep saved run.'})
    write_json(OUT/'nfdi4ing-services.json', services)
    write_json(OUT/'data/model.json', model)
    (OUT/'data/model.js').write_text('window.HELE_SHAW = ' + json.dumps(model, ensure_ascii=False, sort_keys=True, separators=(',',':')) + ';\n')
    (OUT/'model.ttl').write_text(stable_turtle(g))
    (OUT/'vocabulary.ttl').write_text(stable_turtle(vocab))
    jsonld = json.loads(g.serialize(format='json-ld', auto_compact=False))
    for node in jsonld:
        for prop, values in node.items():
            if isinstance(values, list):
                node[prop] = sorted(values, key=lambda x:json.dumps(x, sort_keys=True))
    jsonld.sort(key=lambda n:n.get('@id',''))
    write_json(OUT/'model.jsonld', jsonld)
    print(f'Built {len(entities)} entities, {len(edges)} edges, {len(g)} RDF triples; crosswalk {len(vertices)} vertices / {len(diagram_edges)} edges.')


if __name__ == '__main__':
    main()
