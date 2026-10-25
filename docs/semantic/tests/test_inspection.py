"""Read-only checks for the cheap inspection's evidence and saved execution."""
import base64
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import unittest

import nbformat
from bs4 import BeautifulSoup

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location("build_inspection", HERE / "tools/build_inspection.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class InspectionEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.notebook = nbformat.read(HERE / "notebooks/inspect_results.ipynb", as_version=4)
        cls.manifest = json.loads((HERE / "data/python-inspection-manifest.json").read_text())
        cls.walkthrough = json.loads((ROOT / "notebooks/Simulation_Walkthrough.ipynb").read_text())

    def test_saved_cells_and_pinned_sources(self):
        builder.validate_saved(self.notebook, self.manifest["sources"])
        self.assertEqual(self.manifest["codeCellsExecuted"], 5)
        self.assertFalse(self.manifest["simulationExecuted"])
        self.assertFalse(self.manifest["originalNotebookExecuted"])
        self.assertFalse(self.manifest["uploadExecuted"])

    def test_table_fidelity_and_missing_values(self):
        source = BeautifulSoup("".join(self.walkthrough["cells"][23]["outputs"][0]["data"]["text/html"]), "html.parser")
        names = [c.get_text(strip=True) for c in source.select("thead tr:first-child th")][1:]
        expected = {r.find("th").get_text(): dict(zip(names, [c.get_text() for c in r.find_all("td")])) for r in source.select("tbody tr")}
        rows = list(csv.DictReader(io.StringIO((HERE / "data/inspection/recorded-metrics.csv").read_text())))
        self.assertEqual(len(rows), 3)
        missing = 0
        for row in rows:
            for metric, value in expected[row["configuration"]].items():
                if value == "None":
                    self.assertEqual(row[metric], "")
                    missing += 1
                else:
                    self.assertEqual(float(row[metric]), float(value))
        self.assertEqual(missing, 9)

    def test_recomputed_decisions_match_saved_transcript(self):
        text = "".join(self.walkthrough["cells"][24]["outputs"][0]["text"])
        expected = {}
        cfg = None
        for line in text.splitlines():
            match = re.search(r"Smoke test: configuration (\d+)", line)
            if match:
                cfg = match.group(1)
            match = re.match(r"compare.py: (\w+): (PASS|FAIL|SKIP)", line)
            if match:
                expected[cfg, match.group(1)] = match.group(2)
        rows = list(csv.DictReader(io.StringIO((HERE / "data/inspection/recomputed-comparisons.csv").read_text())))
        self.assertEqual(len(rows), 21)
        self.assertEqual({(r["configuration"], r["metric"]): r["status"] for r in rows}, expected)
        self.assertEqual(sum(r["status"] == "SKIP" for r in rows), 9)
        self.assertEqual((HERE / "data/inspection/original-regression-transcript.txt").read_text(), text)

    def test_original_curve_images_are_byte_exact(self):
        provenance = json.loads((HERE / "data/inspection/provenance.json").read_text())
        self.assertFalse(provenance["numericTrajectoriesAvailable"])
        self.assertEqual(len(provenance["savedImages"]), 6)
        for entry in provenance["savedImages"]:
            source = self.walkthrough["cells"][entry["sourceCellIndex"]]["outputs"][entry["sourceOutputIndex"]]["data"]["image/png"]
            decoded = base64.b64decode(source)
            self.assertEqual((HERE / "data/inspection" / entry["file"]).read_bytes(), decoded)
            self.assertEqual(entry["sha256"], hashlib.sha256(decoded).hexdigest())
        executed_images = [base64.b64decode(o["data"]["image/png"]) for c in self.notebook.cells if c.cell_type == "code"
                           for o in c.outputs if "image/png" in o.get("data", {})]
        self.assertEqual(len(executed_images), 7)
        self.assertEqual(executed_images[0], (HERE / "data/inspection/recorded-outcomes.png").read_bytes())
        for actual, entry in zip(executed_images[1:], provenance["savedImages"]):
            self.assertEqual(actual, (HERE / "data/inspection" / entry["file"]).read_bytes())

    def test_preview_anchors_and_offline_rendering(self):
        soup = BeautifulSoup((HERE / "notebooks/inspect_results.html").read_text(), "html.parser")
        self.assertEqual(len(soup.find_all("img")), 7)
        self.assertFalse(soup.find_all("script"))
        for section in self.manifest["sections"]:
            heading = soup.find(id=section["previewAnchor"])
            self.assertIsNotNone(heading)
            self.assertIn(section["heading"], heading.get_text())
            self.assertEqual(section["anchor"], section["heading"].replace(" ", "-"))
        for element in soup.select("[src], link[href]"):
            url = element.get("src", element.get("href", ""))
            self.assertFalse(url.startswith(("https:", "http:", "//")))

    def test_notebook_has_no_simulation_or_external_execution(self):
        code = "\n".join(c.source for c in self.notebook.cells if c.cell_type == "code")
        self.assertNotRegex(code, r"subprocess|os\.system|requests\.|urllib|!pip|!git|run_simulation|exec\(")
        self.assertIn('json.loads((ROOT / "notebooks/Simulation_Walkthrough.ipynb").read_text())', code)


if __name__ == "__main__":
    unittest.main()
