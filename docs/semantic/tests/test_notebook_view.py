# SPDX-FileCopyrightText: 2026 Vasiliy Seibert
# SPDX-License-Identifier: MIT
"""Guard against silently changing saved scientific evidence during rendering."""
import importlib.util
import json
from pathlib import Path
import unittest

from bs4 import BeautifulSoup
import nbformat

SITE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('notebook_view', SITE / 'tools/notebook_view.py')
view = importlib.util.module_from_spec(spec)
spec.loader.exec_module(view)


class SavedEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.notebook = nbformat.read(view.SOURCE, as_version=4)
        cls.page = view.VIEW.read_text()
        cls.manifest = json.loads(view.MANIFEST.read_text())

    def test_committed_view_preserves_saved_evidence(self):
        report = view.validate_view(self.notebook, self.page, self.manifest)
        self.assertEqual(report['savedImagesVerified'], 9)
        self.assertEqual(report['outputsVerified'], 47)
        self.assertFalse(report['executedByBuild'])

    def test_changed_code_is_rejected(self):
        soup = BeautifulSoup(self.page, 'html.parser')
        soup.select_one('.input_area pre').append('\nprint("changed source")')
        with self.assertRaisesRegex(AssertionError, 'Code changed'):
            view.validate_view(self.notebook, str(soup), self.manifest)

    def test_missing_saved_image_is_rejected(self):
        soup = BeautifulSoup(self.page, 'html.parser')
        images = soup.select('.output_png img')
        # Replacing one saved figure with another is a plausible silent
        # presentation bug even when counts, dimensions and MIME types match.
        images[0]['src'] = images[1]['src']
        with self.assertRaisesRegex(AssertionError, 'Figure changed'):
            view.validate_view(self.notebook, str(soup), self.manifest)

    def test_changed_saved_output_is_rejected(self):
        soup = BeautifulSoup(self.page, 'html.parser')
        stream = soup.select_one('.output_stream pre')
        stream.append('\nIncorrectly reported success')
        with self.assertRaisesRegex(AssertionError, 'Stream changed'):
            view.validate_view(self.notebook, str(soup), self.manifest)

    def test_replaced_missing_metric_is_rejected(self):
        soup = BeautifulSoup(self.page, 'html.parser')
        tables = soup.select('.output_html table')
        metric = next(td for table in tables for td in table.select('td') if td.get_text() == 'None')
        metric.string = '0.21'
        with self.assertRaisesRegex(AssertionError, 'Table changed'):
            view.validate_view(self.notebook, str(soup), self.manifest)


if __name__ == '__main__':
    unittest.main()
