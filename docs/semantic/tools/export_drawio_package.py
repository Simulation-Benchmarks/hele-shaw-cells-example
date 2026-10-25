#!/usr/bin/env python3
"""Refresh the portable drawing snapshot from the maintained atlas sources.

SPDX-FileCopyrightText: 2026 Vasiliy Seibert
SPDX-License-Identifier: MIT
"""
from pathlib import Path
import shutil
import subprocess
import sys

SITE = Path(__file__).resolve().parents[1]
REPO = SITE.parents[1]
PACKAGE = REPO / 'docs/drawio-html'


def main():
    PACKAGE.mkdir(exist_ok=True)
    copies = {
        REPO / 'Validation.drawio': 'Validation.drawio',
        SITE / 'source/drawio-links.json': 'drawio-links.json',
        SITE / 'source/diagram-crosswalk.json': 'diagram-crosswalk.json',
        SITE / 'drawio-viewer.js': 'drawio-viewer.js',
        SITE / 'tokens.css': 'tokens.css',
    }
    for source, name in copies.items():
        shutil.copyfile(source, PACKAGE / name)
    shutil.copytree(SITE / 'vendor', PACKAGE / 'vendor', dirs_exist_ok=True)
    subprocess.run([sys.executable, str(PACKAGE / 'build.py')], check=True)
    subprocess.run([sys.executable, str(PACKAGE / 'build.py'), '--check'], check=True)


if __name__ == '__main__':
    main()
