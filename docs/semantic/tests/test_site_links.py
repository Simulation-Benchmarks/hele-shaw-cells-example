"""Check that generated site evidence links work independently of GitHub Pages."""
import json
from pathlib import Path
import unittest
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup


SITE = Path(__file__).resolve().parents[1]


class SiteLinks(unittest.TestCase):
    def check_local_url(self, url, base=SITE):
        parts = urlsplit(url)
        if parts.scheme or parts.netloc or not parts.path:
            return
        target = (base / unquote(parts.path)).resolve()
        self.assertTrue(target.is_relative_to(SITE), f"Link escapes published site: {url}")
        self.assertTrue(target.is_file(), f"Missing local destination: {url}")
        if parts.fragment and target.suffix == '.html':
            # index.html has application hash routes; notebook links have real anchors.
            if target.name != 'index.html':
                doc = BeautifulSoup(target.read_text(), 'html.parser')
                self.assertIsNotNone(doc.find(id=unquote(parts.fragment)), f"Missing section: {url}")

    def test_static_resources_and_notebook_destinations(self):
        for path in [SITE / 'index.html', *sorted((SITE / 'notebooks').glob('*.html'))]:
            doc = BeautifulSoup(path.read_text(), 'html.parser')
            for tag in doc.select('[src], link[href], a[href]'):
                url = tag.get('src') or tag.get('href')
                with self.subTest(document=str(path.relative_to(SITE)), url=url[:120]):
                    if tag.name in ('script', 'img', 'link'):
                        self.assertFalse(url.startswith(('https://', 'http://', '//')),
                                         'Published rendering must not require remote resources')
                    self.check_local_url(url, path.parent)

    def test_model_actions_and_notebook_sections(self):
        model = json.loads((SITE / 'data/model.json').read_text())
        for entity in model['entities']:
            for key in ('previewUrl', 'launchUrl'):
                if entity.get(key):
                    with self.subTest(entity=entity['id'], action=key):
                        self.check_local_url(entity[key])
        for workflow in model['workflows']:
            for action in workflow.get('actions', []):
                with self.subTest(workflow=workflow['slug'], action=action['label']):
                    self.check_local_url(action['url'])


if __name__ == '__main__':
    unittest.main()
