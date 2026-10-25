# SPDX-FileCopyrightText: 2026 Vasiliy Seibert
# SPDX-License-Identifier: MIT
"""Portable-folder acceptance checks, independent of the atlas build process."""
import csv
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import urljoin, urlsplit
import xml.etree.ElementTree as ET


SITE = Path(__file__).resolve().parents[1]
REPO = SITE.parents[1]
PACKAGE = REPO / 'docs/drawio-html'
GENERATED = ('data.js', 'Validation.linked.drawio', 'mapping.csv', 'manifest.json')
spec = importlib.util.spec_from_file_location('package_xml_validator', SITE / 'tools/validate_drawio.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class DrawioPackageTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='hele-shaw-portable-')
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name) / 'drawing'
        shutil.copytree(PACKAGE, self.folder,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.DS_Store'))
        self.original = (self.folder / 'Validation.drawio').read_bytes()

    def mapping(self):
        return json.loads((self.folder / 'drawio-links.json').read_text())

    def save_mapping(self, mapping):
        (self.folder / 'drawio-links.json').write_text(json.dumps(mapping, indent=2) + '\n')

    def build(self, *arguments):
        # Isolated mode and no site packages demonstrate the stdlib-only contract.
        # No repository working directory, Git executable, or PYTHONPATH is usable.
        environment = os.environ.copy()
        environment['PATH'] = ''
        environment.pop('PYTHONPATH', None)
        return subprocess.run([sys.executable, '-I', '-S', str(self.folder / 'build.py'), *arguments],
                              cwd=self.folder.parent, env=environment, text=True,
                              capture_output=True, timeout=30)

    def assert_build_succeeds(self, *arguments):
        result = self.build(*arguments)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def assert_rejected_without_rewriting_outputs(self, message):
        before = {name: (self.folder / name).read_bytes() for name in GENERATED}
        result = self.build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(message, result.stderr)
        self.assertEqual(before, {name: (self.folder / name).read_bytes() for name in GENERATED})

    def test_portable_original_and_every_graphical_cell_have_matching_links(self):
        self.assertEqual(self.original, (REPO / 'Validation.drawio').read_bytes())
        self.assertEqual(hashlib.sha256(self.original).hexdigest(), validator.SOURCE_SHA256)
        root = ET.fromstring(self.original)
        cells = root.findall('.//mxCell')
        graphical = {cell.get('id'): cell for cell in cells
                     if cell.get('vertex') == '1' or cell.get('edge') == '1'}
        self.assertEqual(len(cells), 214)
        self.assertEqual(sum(cell.get('vertex') == '1' for cell in graphical.values()), 112)
        self.assertEqual(sum(cell.get('edge') == '1' for cell in graphical.values()), 100)

        payload = validator.read_projection(self.folder / 'data.js')
        self.assertEqual(payload['xml'].encode('utf-8'), self.original)
        linked = validator.verify_linked_xml(self.original,
                                             (self.folder / 'Validation.linked.drawio').read_bytes())
        rows = list(csv.DictReader(io.StringIO((self.folder / 'mapping.csv').read_text())))
        self.assertEqual(len(rows), 212)
        self.assertEqual(set(payload['links']), set(graphical))
        self.assertEqual(set(linked), set(graphical))
        self.assertEqual({row['diagramId'] for row in rows}, set(graphical))
        for row in rows:
            identifier = row['diagramId']
            self.assertEqual(row['url'], payload['links'][identifier]['url'])
            self.assertEqual(row['url'], linked[identifier])
            self.assertEqual(urlsplit(row['url']).scheme, 'https')
            self.assertTrue(urlsplit(row['url']).hostname)

    def test_copied_folder_rebuilds_reproducibly_without_repository_or_dependencies(self):
        self.assertFalse((self.folder / '.git').exists())
        for name in GENERATED:
            (self.folder / name).unlink()
        self.assert_build_succeeds()
        self.assert_build_succeeds('--check')
        first = {name: (self.folder / name).read_bytes() for name in GENERATED}
        self.assert_build_succeeds()
        self.assertEqual(first, {name: (self.folder / name).read_bytes() for name in GENERATED})
        self.assertEqual((self.folder / 'Validation.drawio').read_bytes(), self.original)
        manifest = json.loads((self.folder / 'manifest.json').read_text())
        for name, digest in manifest['files'].items():
            self.assertEqual(hashlib.sha256((self.folder / name).read_bytes()).hexdigest(), digest, name)

    def test_missing_link_is_rejected_before_generated_files_change(self):
        mapping = self.mapping()
        del mapping['links']['JDZ3WXQOoo0OTXsIz6hO-6']
        self.save_mapping(mapping)
        self.assert_rejected_without_rewriting_outputs('Every original vertex and edge')

    def test_changed_original_is_rejected_even_for_only_extra_whitespace(self):
        (self.folder / 'Validation.drawio').write_bytes(self.original + b'\n')
        self.assert_rejected_without_rewriting_outputs('Original diagram differs')

    def test_changed_semantic_edge_direction_requires_review(self):
        mapping = self.mapping()
        edge = mapping['links']['eiFgZNk86BmHCPwQhzBy-49']
        edge['mappedSource'], edge['mappedTarget'] = edge['mappedTarget'], edge['mappedSource']
        self.save_mapping(mapping)
        self.assert_rejected_without_rewriting_outputs('Changed semantic interpretation')

    def test_url_edit_reaches_browser_csv_and_drawio_without_mutating_source(self):
        mapping = self.mapping()
        identifier = 'JDZ3WXQOoo0OTXsIz6hO-6'
        destination = 'notebooks/Simulation_Walkthrough.html#inspect-results'
        mapping['links'][identifier]['url'] = destination
        mapping['links'][identifier]['target'] = '_blank'
        self.save_mapping(mapping)
        self.assert_build_succeeds()
        self.assert_build_succeeds('--check')
        self.assertEqual((self.folder / 'Validation.drawio').read_bytes(), self.original)
        expected = urljoin(mapping['meta']['publishedBaseUrl'], destination)
        payload = validator.read_projection(self.folder / 'data.js')
        self.assertEqual(payload['links'][identifier]['url'], expected)
        self.assertEqual(payload['links'][identifier]['target'], '_blank')
        linked_xml = (self.folder / 'Validation.linked.drawio').read_bytes()
        self.assertEqual(validator.verify_linked_xml(self.original, linked_xml)[identifier], expected)
        wrapper = ET.fromstring(linked_xml).find(f'.//UserObject[@id="{identifier}"]')
        self.assertEqual(wrapper.get('linkTarget'), '_blank')
        rows = {row['diagramId']: row for row in csv.DictReader(
            io.StringIO((self.folder / 'mapping.csv').read_text()))}
        self.assertEqual(rows[identifier]['url'], expected)


if __name__ == '__main__':
    unittest.main()
