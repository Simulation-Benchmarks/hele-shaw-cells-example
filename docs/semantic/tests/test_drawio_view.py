# SPDX-FileCopyrightText: 2026 Vasiliy Seibert
# SPDX-License-Identifier: MIT
"""Independent regressions for lossless draw.io rendering and navigation."""
import copy
import importlib.util
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

SITE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('validate_drawio', SITE / 'tools/validate_drawio.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class DrawioViewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = validator.load_payload()

    def test_complete_original_and_linked_view(self):
        result = validator.validate_payload(**self.payload)
        self.assertEqual(result['vertexCount'], 112)
        self.assertEqual(result['edgeCount'], 100)
        self.assertEqual(result['linksVerified'], 212)
        self.assertTrue(result['sourceUnchanged'])

    def test_source_byte_change_is_rejected(self):
        payload = copy.deepcopy(self.payload)
        payload['original'] += b'\n'
        with self.assertRaisesRegex(AssertionError, 'original Validation.drawio changed'):
            validator.validate_payload(**payload)

    def test_runtime_relayout_is_rejected(self):
        payload = copy.deepcopy(self.payload)
        runtime = ET.fromstring(payload['projection']['xml'])
        geometry = next(runtime.iter('mxGeometry'))
        geometry.set('x', '999')
        payload['projection']['xml'] = ET.tostring(runtime, encoding='unicode')
        with self.assertRaisesRegex(AssertionError, 'Runtime XML'):
            validator.validate_payload(**payload)

    def test_linked_vertex_style_change_is_rejected(self):
        linked = ET.fromstring(self.payload['linked'])
        vertex = next(cell for cell in linked.iter('mxCell') if cell.get('vertex') == '1')
        vertex.set('style', vertex.get('style', '') + 'fillColor=#ff0000;')
        with self.assertRaisesRegex(AssertionError, 'styles'):
            validator.verify_linked_xml(self.payload['original'], ET.tostring(linked))

    def test_nested_edge_waypoint_change_is_rejected(self):
        linked = ET.fromstring(self.payload['linked'])
        point = next(linked.iter('mxPoint'))
        point.set('x', '12345')
        with self.assertRaisesRegex(AssertionError, 'geometry'):
            validator.verify_linked_xml(self.payload['original'], ET.tostring(linked))

    def test_changed_edge_endpoint_is_rejected(self):
        linked = ET.fromstring(self.payload['linked'])
        edge = next(cell for cell in linked.iter('mxCell') if cell.get('edge') == '1')
        edge.set('target', edge.get('source'))
        with self.assertRaisesRegex(AssertionError, 'endpoints'):
            validator.verify_linked_xml(self.payload['original'], ET.tostring(linked))

    def test_wrong_relationship_destination_is_rejected(self):
        payload = copy.deepcopy(self.payload)
        identifier = next(k for k, v in payload['projection']['links'].items() if 'relationshipId' in v)
        for field in ('projection', 'manifest'):
            payload[field]['links'][identifier]['url'] = '#relationship/nonexistent'
        with self.assertRaisesRegex(AssertionError, 'Wrong relationship route'):
            validator.validate_payload(**payload)

    def test_missing_cell_link_is_rejected(self):
        payload = copy.deepcopy(self.payload)
        identifier = next(iter(payload['projection']['links']))
        del payload['projection']['links'][identifier]
        del payload['manifest']['links'][identifier]
        with self.assertRaisesRegex(AssertionError, 'every original vertex and edge'):
            validator.validate_payload(**payload)

    def test_wrong_pinned_source_revision_is_rejected(self):
        payload = copy.deepcopy(self.payload)
        identifier = next(k for k, v in payload['projection']['links'].items() if v.get('sourcePath'))
        for field in ('projection', 'manifest'):
            payload[field]['links'][identifier]['sourceRevision'] = 'main'
        with self.assertRaisesRegex(AssertionError, 'unreviewed revision'):
            validator.validate_payload(**payload)

    def test_unknown_saved_notebook_anchor_is_rejected(self):
        payload = copy.deepcopy(self.payload)
        identifier = next(k for k, v in payload['projection']['links'].items() if v.get('linkKind') == 'saved-evidence')
        for field in ('projection', 'manifest'):
            payload[field]['links'][identifier]['url'] = 'notebooks/Simulation_Walkthrough.html#invented-output'
        with self.assertRaisesRegex(AssertionError, 'verified saved preview'):
            validator.validate_payload(**payload)

    def test_pinned_renderer_and_offline_bootstrap(self):
        report = validator.validate_offline_renderer()
        self.assertEqual(report['officialRendererVersion'], '29.6.6')
        self.assertTrue(report['offlineBootstrapOrderVerified'])

    def test_remote_bootstrap_dependency_is_rejected(self):
        source = (SITE / 'index.html').read_text()
        source = source.replace('src="app.js"', 'src="https://example.invalid/app.js"')
        with self.assertRaisesRegex(AssertionError, 'must be local'):
            validator.validate_offline_renderer(index_text=source)

    def test_offline_config_after_viewer_is_rejected(self):
        source = (SITE / 'index.html').read_text()
        first = 'vendor/drawio/29.6.6/offline-config.js'
        second = 'vendor/drawio/29.6.6/viewer-static.min.js'
        source = source.replace(first, 'TEMP_SCRIPT').replace(second, first).replace('TEMP_SCRIPT', second)
        with self.assertRaisesRegex(AssertionError, 'must precede'):
            validator.validate_offline_renderer(index_text=source)

    def test_math_enabled_source_is_rejected(self):
        original = ET.fromstring(self.payload['original'])
        next(original.iter('mxGraphModel')).set('math', '1')
        with self.assertRaisesRegex(AssertionError, 'math="0"'):
            validator.validate_offline_renderer(original=ET.tostring(original))

    def test_missing_math_sentinel_is_rejected(self):
        offline = (SITE / 'vendor/drawio/29.6.6/offline-config.js').read_text()
        offline = offline.replace('heleShawDisabled: true', 'heleShawDisabled: false')
        with self.assertRaisesRegex(AssertionError, 'sentinel is missing'):
            validator.validate_offline_renderer(offline_text=offline)


if __name__ == '__main__':
    unittest.main()
