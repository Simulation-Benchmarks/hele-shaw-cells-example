#!/usr/bin/env python3
# Extracts a still frame from the reference AVI for use in the docs. Does not modify any source files.
#
# Usage:  scripts/extract_reference_frame.py [--input PATH] [--output PATH]
#                                            [--frame-index N] [--max-size PIXELS]
#
# Defaults: reads the AVI from the runnable repo (with a fallback to the example
# repo's case_template copy), picks frame 200 (~t=10s, fingers well-developed),
# crops to the disk's bounding box, resizes the larger dimension to 400 px, and
# saves a small PNG to docs/hele-shaw-cells.png.
#
# Requires: imageio[ffmpeg] and Pillow (both pure-Python pip installs).
#     python3 -m pip install --user "imageio[ffmpeg]" pillow

import argparse
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image
import imageio.v3 as iio

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_INPUT_PRIMARY = Path(
    "/Users/vasiliy/Documents/GitHub/V-V-Betty/hele-shaw-cells-runnable/"
    "testcase/Results/sim_260429_Air-Soap_s 0_031 F 4e-7 zeroGradient.avi"
)
DEFAULT_INPUT_FALLBACK = (
    REPO_ROOT
    / "openfoam"
    / "case_template"
    / "Results"
    / "sim_260429_Air-Soap_s 0_031 F 4e-7 zeroGradient.avi"
)
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "hele-shaw-cells.png"


def resolve_input(user_path: str | None) -> Path:
    if user_path:
        p = Path(user_path)
        if not p.exists():
            sys.exit(f"extract_reference_frame.py: --input not found: {p}")
        return p
    if DEFAULT_INPUT_PRIMARY.exists():
        return DEFAULT_INPUT_PRIMARY
    if DEFAULT_INPUT_FALLBACK.exists():
        return DEFAULT_INPUT_FALLBACK
    sys.exit(
        "extract_reference_frame.py: neither default AVI path exists.\n"
        f"  tried: {DEFAULT_INPUT_PRIMARY}\n"
        f"  tried: {DEFAULT_INPUT_FALLBACK}\n"
        "  pass --input PATH explicitly."
    )


def crop_to_disk(frame: np.ndarray, margin: int = 20) -> np.ndarray:
    """Crop to the widest contiguous run of non-white columns (the simulation disk)."""
    h, w, _ = frame.shape
    r, g, b = frame[..., 0], frame[..., 1], frame[..., 2]
    non_white = (r < 240) | (g < 240) | (b < 240)

    col_sums = non_white.sum(axis=0)
    threshold = col_sums.max() * 0.3
    big = col_sums > threshold

    runs: list[tuple[int, int, int]] = []
    in_run = False
    start = 0
    for i, v in enumerate(big):
        if v and not in_run:
            start = i
            in_run = True
        elif not v and in_run:
            runs.append((start, i - 1, i - start))
            in_run = False
    if in_run:
        runs.append((start, len(big) - 1, len(big) - start))
    if not runs:
        return frame

    runs.sort(key=lambda x: -x[2])
    x0, x1, _ = runs[0]

    disk_rows = non_white[:, x0:x1 + 1].any(axis=1)
    ys = np.where(disk_rows)[0]
    if len(ys) == 0:
        return frame
    y0, y1 = int(ys.min()), int(ys.max())

    y0 = max(0, y0 - margin)
    y1 = min(h - 1, y1 + margin)
    x0 = max(0, x0 - margin)
    x1 = min(w - 1, x1 + margin)
    return frame[y0:y1 + 1, x0:x1 + 1]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract a still frame from the reference AVI for use in the docs.",
    )
    parser.add_argument("--input", help="path to source AVI (defaults to runnable repo, then example case_template)")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="output PNG path (default: docs/hele-shaw-cells.png)")
    parser.add_argument("--frame-index", type=int, default=200, help="frame index to extract (default: 200, ~t=10s)")
    parser.add_argument("--max-size", type=int, default=400, help="larger dimension of output in pixels (default: 400)")
    args = parser.parse_args()

    src = resolve_input(args.input)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    print(f"extract_reference_frame.py: reading {src}")
    frame = iio.imread(str(src), index=args.frame_index)
    print(f"  frame {args.frame_index} shape: {frame.shape}")

    cropped = crop_to_disk(frame)
    print(f"  cropped shape: {cropped.shape}")

    img = Image.fromarray(cropped)
    img.thumbnail((args.max_size, args.max_size), Image.LANCZOS)
    img.save(out, optimize=True)

    size_kb = os.path.getsize(out) / 1024
    print(f"extract_reference_frame.py: wrote {out} ({img.size[0]}x{img.size[1]}, {size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
