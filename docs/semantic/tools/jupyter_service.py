# SPDX-FileCopyrightText: 2026 Vasiliy Seibert
# SPDX-License-Identifier: MIT
"""Return the NFDI4Ing launch destination only after recorded Hub verification.

Adapted from FAIR4SD's MIT-licensed semantic viewer tooling. The public route
opens a file in each visitor's own server; it does not distribute the notebook.
The saved HTML view remains available when the destination is not configured.
"""
from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
from urllib.parse import quote, urlsplit


HERE = Path(__file__).resolve().parents[1]
SERVICE_HOST = 'jupyter-nfdi.tik.uni-stuttgart.de'
WORKSPACE = 'hele-shaw-inspection'
NOTEBOOK_PATH = 'work/hele-shaw-cells-example/docs/semantic/notebooks/inspect_results.ipynb'
SHAREABLE_PATH = f'/hub/user-redirect/lab/workspaces/{WORKSPACE}/tree/{NOTEBOOK_PATH}'
SHAREABLE_URL = f'https://{SERVICE_HOST}{SHAREABLE_PATH}'
SETUP_URL = ('https://github.com/Simulation-Benchmarks/hele-shaw-cells-example/'
             'blob/main/docs/semantic/JUPYTER.md')


def setup_url():
    """Return the public first-use guide independently of launch verification."""
    return SETUP_URL


def _read_json(path: Path, description: str):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise ValueError(f'Missing or unreadable {description}: {path.name}.') from exc


def _require(condition: bool, message: str):
    if not condition:
        raise ValueError(message)


def notebook_url(section=None, *, here=HERE):
    """Return a verified notebook/heading URL, or None when unconfigured.

    ``section`` may be a heading anchor string or a mapping containing ``anchor``.
    ``here`` is the semantic-site directory; callers normally omit it. Activation
    requires the source notebook hash, five successful code cells, runtime
    versions, and actual heading-navigation evidence in jupyter-validation.json.
    """
    here = Path(here)
    config = _read_json(here / 'jupyter.json', 'Jupyter destination configuration')
    _require(isinstance(config, dict) and 'notebookUrl' in config,
             'Jupyter configuration must contain notebookUrl; use null until verified.')
    url = config['notebookUrl']
    if url is None:
        return None
    _require(isinstance(url, str), 'The Jupyter notebook URL must be a string or null.')
    parsed = urlsplit(url)
    _require(parsed.scheme == 'https' and parsed.netloc == SERVICE_HOST
             and parsed.path == SHAREABLE_PATH and not parsed.query and not parsed.fragment
             and url == SHAREABLE_URL,
             'Use the NFDI4Ing shareable Hele-Shaw notebook URL without a query or fragment.')

    notebook_path = here / 'notebooks/inspect_results.ipynb'
    try:
        notebook_bytes = notebook_path.read_bytes()
        notebook = json.loads(notebook_bytes)
    except (OSError, ValueError) as exc:
        raise ValueError('The inspection notebook is missing or unreadable.') from exc
    digest = hashlib.sha256(notebook_bytes).hexdigest()
    _require(config.get('verifiedNotebookSha256') == digest,
             'The notebook has changed or its NFDI4Ing copy is unverified. '
             'Update the Hub copy and verify it before enabling launch links.')
    _require(isinstance(notebook, dict) and isinstance(notebook.get('cells'), list),
             'The inspection notebook must contain notebook cells.')
    code_cells = [cell for cell in notebook['cells']
                  if isinstance(cell, dict) and cell.get('cell_type') == 'code']
    _require(len(code_cells) == 5, 'The inspection workflow must contain five code cells.')

    manifest = _read_json(here / 'data/python-inspection-manifest.json', 'inspection manifest')
    sections = manifest.get('sections', []) if isinstance(manifest, dict) else []
    anchors = [entry.get('anchor') for entry in sections if isinstance(entry, dict)]
    _require(len(sections) == len(anchors) == 5
             and all(isinstance(anchor, str) and anchor.strip() for anchor in anchors)
             and len(set(anchors)) == 5,
             'The inspection manifest must contain five unique heading anchors.')

    evidence = _read_json(here / 'jupyter-validation.json', 'Jupyter verification evidence')
    _require(isinstance(evidence, dict), 'Jupyter verification evidence must be an object.')
    try:
        verified_on = evidence.get('verifiedOn')
        _require(isinstance(verified_on, str), 'Record the Hub verification date in verifiedOn.')
        date.fromisoformat(verified_on)
    except (TypeError, ValueError) as exc:
        raise ValueError('Record the Hub verification date in YYYY-MM-DD format.') from exc
    _require(evidence.get('sourceNotebookSha256') == digest,
             'Hub verification evidence does not match the source notebook checksum.')
    _require(evidence.get('notebookPath') == NOTEBOOK_PATH,
             'Hub verification evidence must identify the same notebook path.')
    runtime = evidence.get('runtime', {})
    _require(isinstance(runtime, dict)
             and all(isinstance(runtime.get(name), str) and runtime[name].strip()
                     for name in ('python', 'numpy', 'pandas', 'matplotlib')),
             'Record the verified Python, NumPy, Pandas and Matplotlib versions.')
    execution = evidence.get('execution', {})
    _require(isinstance(execution, dict), 'Record the Hub execution checks.')
    counts = execution.get('codeCellCounts', [])
    _require(isinstance(counts, list) and len(counts) == 5
             and all(type(count) is int and count > 0 for count in counts)
             and all(a < b for a, b in zip(counts, counts[1:]))
             and type(execution.get('errorOutputs')) is int and execution['errorOutputs'] == 0
             and execution.get('simulationExecuted') is False,
             'Verify all five code cells in order, with no errors and no simulation execution.')
    navigation = evidence.get('navigation', {})
    _require(isinstance(navigation, dict)
             and navigation.get('workspace') == WORKSPACE
             and navigation.get('target') == '_self'
             and navigation.get('sectionsVerified') == anchors
             and isinstance(navigation.get('method'), str) and navigation['method'].strip(),
             'Verify all five exact heading links in the same-tab Hele-Shaw workspace.')

    if section is None:
        return url
    anchor = section.get('anchor') if isinstance(section, dict) else section
    _require(isinstance(anchor, str) and anchor in anchors,
             'The requested notebook heading is not one of the verified sections.')
    # JupyterLab documents the empty query before a heading fragment. A dedicated
    # same-tab workspace avoids auto-cloned duplicate workspaces losing fragments.
    return url + '?#' + quote(anchor, safe='-._~')
