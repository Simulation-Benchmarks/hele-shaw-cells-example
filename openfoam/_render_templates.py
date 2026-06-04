"""Render all *.template files under case_template/ into a target directory.

Used by run_simulation.py, build_benchmark_zip.py, and the smoke test in
tests/. Files that do NOT have a .template suffix are copied verbatim.

This is the single source of templating logic for the Hele-Shaw example.
The template syntax is Jinja2 with default delimiters: {{ var.path }}.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined


def render_case_template(
    case_template_dir: Path,
    parameters: dict,
    target_dir: Path,
) -> list[Path]:
    """Render the case_template tree into target_dir.

    Walks case_template_dir recursively. For each .template file, strips
    the suffix and renders with Jinja2 (StrictUndefined: missing keys
    raise). For non-template files, copies verbatim.

    Returns the list of files written, relative to target_dir.
    """
    case_template_dir = Path(case_template_dir).resolve()
    target_dir = Path(target_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(str(case_template_dir)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        autoescape=False,
    )

    written: list[Path] = []
    for src in sorted(case_template_dir.rglob("*")):
        if not src.is_file():
            continue
        rel = src.relative_to(case_template_dir)
        if src.suffix == ".template":
            out_name = rel.stem
            out_rel = rel.parent / out_name
            template = env.get_template(str(rel))
            rendered = template.render(**parameters)
            out_path = target_dir / out_rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(rendered)
        else:
            out_path = target_dir / rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, out_path)
        written.append(out_path.relative_to(target_dir))
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--case-template-dir", required=True, type=Path)
    ap.add_argument("--parameters-file", required=True, type=Path)
    ap.add_argument("--target-dir", required=True, type=Path)
    args = ap.parse_args()

    parameters = json.loads(args.parameters_file.read_text())
    written = render_case_template(
        args.case_template_dir, parameters, args.target_dir
    )
    for rel in written:
        print(rel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
