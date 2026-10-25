# SPDX-FileCopyrightText: 2026 Vasiliy Seibert
# SPDX-License-Identifier: MIT
"""Reject launch links that outlive the notebook or its Hub verification."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import quote


SITE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('jupyter_service', SITE / 'tools/jupyter_service.py')
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


class JupyterDestinationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.here = Path(self.temp.name)
        (self.here / 'notebooks').mkdir()
        (self.here / 'data').mkdir()
        self.anchors = [f'{number}.-Inspect-α-{number}' for number in range(1, 6)]
        self.notebook = {'cells': [dict(cell_type='code', source=['pass\n']) for _ in range(5)]}
        self.write('notebooks/inspect_results.ipynb', self.notebook)
        digest = hashlib.sha256((self.here / 'notebooks/inspect_results.ipynb').read_bytes()).hexdigest()
        self.config = dict(notebookUrl=service.SHAREABLE_URL, verifiedNotebookSha256=digest)
        self.evidence = dict(
            verifiedOn='2026-10-25', sourceNotebookSha256=digest,
            notebookPath=service.NOTEBOOK_PATH,
            runtime=dict(python='3.13.11', numpy='2.3.5', pandas='2.3.3', matplotlib='3.10.8'),
            execution=dict(codeCellCounts=[1, 2, 3, 4, 5], errorOutputs=0, simulationExecuted=False),
            navigation=dict(workspace=service.WORKSPACE, target='_self',
                            sectionsVerified=self.anchors,
                            method='Clicked all workflow section links in the authenticated Hub.'),
        )
        self.manifest = dict(sections=[dict(anchor=anchor) for anchor in self.anchors])
        self.save()

    def write(self, path, value):
        (self.here / path).write_text(json.dumps(value), encoding='utf-8')

    def save(self):
        self.write('jupyter.json', self.config)
        self.write('jupyter-validation.json', self.evidence)
        self.write('data/python-inspection-manifest.json', self.manifest)

    def test_unconfigured_destination_needs_no_notebook_or_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            here = Path(directory)
            (here / 'jupyter.json').write_text('{"notebookUrl":null}')
            self.assertIsNone(service.notebook_url(here=here))
            self.assertIsNone(service.notebook_url('any-section', here=here))

    def test_verified_destination_and_string_or_mapping_sections(self):
        self.assertEqual(service.notebook_url(here=self.here), service.SHAREABLE_URL)
        for anchor in self.anchors:
            expected = service.SHAREABLE_URL + '?#' + quote(anchor, safe='-._~')
            self.assertEqual(service.notebook_url(anchor, here=self.here), expected)
            self.assertEqual(service.notebook_url({'anchor': anchor}, here=self.here), expected)

    def test_setup_guide_is_independent_of_launch_configuration(self):
        self.assertEqual(service.setup_url(), service.SETUP_URL)
        self.assertEqual(service.setup_url(),
                         'https://github.com/Simulation-Benchmarks/hele-shaw-cells-example/'
                         'blob/main/docs/semantic/JUPYTER.md')

    def test_personal_or_noncanonical_urls_are_rejected(self):
        for url in [
            service.SHAREABLE_URL.replace('/hub/user-redirect/', '/user/someone/'),
            service.SHAREABLE_URL.replace(service.WORKSPACE, 'another-workspace'),
            service.SHAREABLE_URL.replace('/work/', '/different-folder/'),
            service.SHAREABLE_URL.replace('https:', 'http:'),
            service.SHAREABLE_URL.replace(service.SERVICE_HOST, service.SERVICE_HOST + '.example.org'),
            service.SHAREABLE_URL + '?reset', service.SHAREABLE_URL + '#heading',
        ]:
            with self.subTest(url=url):
                self.config['notebookUrl'] = url
                self.save()
                with self.assertRaisesRegex(ValueError, 'shareable'):
                    service.notebook_url(here=self.here)

    def test_changed_notebook_invalidates_verified_links(self):
        self.notebook['cells'][0]['source'] = ['print("changed")\n']
        self.write('notebooks/inspect_results.ipynb', self.notebook)
        with self.assertRaisesRegex(ValueError, 'notebook has changed'):
            service.notebook_url(here=self.here)

    def test_missing_or_stale_evidence_is_rejected(self):
        (self.here / 'jupyter-validation.json').unlink()
        with self.assertRaisesRegex(ValueError, 'verification evidence'):
            service.notebook_url(here=self.here)
        self.evidence['sourceNotebookSha256'] = '0' * 64
        self.save()
        with self.assertRaisesRegex(ValueError, 'evidence does not match'):
            service.notebook_url(here=self.here)

    def test_incomplete_or_failed_execution_is_rejected(self):
        for change in [dict(codeCellCounts=[1, 2, 3, 4]), dict(codeCellCounts=[1, 2, 2, 4, 5]),
                       dict(errorOutputs=1), dict(errorOutputs=False), dict(simulationExecuted=True)]:
            with self.subTest(change=change):
                self.evidence['execution'] = dict(codeCellCounts=[1, 2, 3, 4, 5],
                                                 errorOutputs=0, simulationExecuted=False)
                self.evidence['execution'].update(change)
                self.save()
                with self.assertRaisesRegex(ValueError, 'five code cells'):
                    service.notebook_url(here=self.here)

    def test_heading_changes_or_incomplete_navigation_are_rejected(self):
        self.evidence['navigation']['sectionsVerified'] = self.anchors[:4]
        self.save()
        with self.assertRaisesRegex(ValueError, 'five exact heading links'):
            service.notebook_url(here=self.here)
        self.evidence['navigation']['sectionsVerified'] = self.anchors
        self.manifest['sections'][0]['anchor'] = 'new-heading'
        self.save()
        with self.assertRaisesRegex(ValueError, 'five exact heading links'):
            service.notebook_url(here=self.here)

    def test_unknown_sections_are_rejected(self):
        for section in ('missing-heading', '', {}, 1):
            with self.subTest(section=section):
                with self.assertRaisesRegex(ValueError, 'verified sections'):
                    service.notebook_url(section, here=self.here)

    def test_runtime_and_notebook_path_evidence_are_required(self):
        self.evidence['runtime'].pop('numpy')
        self.save()
        with self.assertRaisesRegex(ValueError, 'versions'):
            service.notebook_url(here=self.here)
        self.evidence['runtime']['numpy'] = '2.3.5'
        self.evidence['notebookPath'] = 'someone-else/notebook.ipynb'
        self.save()
        with self.assertRaisesRegex(ValueError, 'same notebook path'):
            service.notebook_url(here=self.here)


if __name__ == '__main__':
    unittest.main()
