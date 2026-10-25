"""Build and validate the static atlas; never execute simulations or notebooks.

SPDX-FileCopyrightText: 2026 Vasiliy Seibert
SPDX-License-Identifier: MIT
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


SITE = Path(__file__).resolve().parents[1]
REPO = SITE.parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=REPO / "_site")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output == REPO or output in SITE.parents or output == SITE or SITE in output.parents:
        parser.error("Output must be a separate build directory, outside the source site.")
    marker = output / ".hele-shaw-site-build"
    if output.exists() and any(output.iterdir()) and not marker.exists():
        parser.error("Refusing to replace a nonempty directory without the site build marker.")
    for name in ("notebook_view.py", "build_inspection.py", "build_model.py", "build_tokens.py", "build_graphs.py", "build_drawio.py", "validate_model.py", "validate_drawio.py", "export_drawio_package.py"):
        subprocess.run([sys.executable, str(SITE / "tools" / name)], cwd=REPO, check=True)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    marker.touch()
    files = ("index.html", "app.js", "drawio-viewer.js", "tokens.css", "style.css", "model.ttl", "model.jsonld",
             "vocabulary.ttl", "shapes.ttl", "validation.json", "nfdi4ing-services.json",
             "ATTRIBUTION.md", "JUPYTER.md", "jupyter.json", "jupyter-validation.json", ".nojekyll")
    for name in files:
        source = SITE / name
        if not source.is_file():
            raise FileNotFoundError(source)
        shutil.copy2(source, output / name)
    for name in ("data", "assets", "notebooks", "source", "vendor"):
        source = SITE / name
        if source.is_dir():
            shutil.copytree(source, output / name)
    shutil.copy2(REPO / "Validation.drawio", output / "Validation.drawio")
    shutil.copytree(REPO / "docs/drawio-html", output / "drawio-html",
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.DS_Store'))
    shutil.make_archive(str(output / "drawio-html"), 'zip', output, 'drawio-html')
    print(f"Validated static site: {output}")


if __name__ == "__main__":
    main()
