"""Skeletonise a binary mask and count fingertip pixels.

A literal port of the rule from
``data-processing-experiment/functions/m_image_processing.py:skel_coords``:

  1. Skeletonise the binary image.
  2. For each skeleton pixel, build its 3x3 neighbourhood and count
     the number of skeleton pixels in it.
  3. A skeleton pixel with EXACTLY 2 non-zero neighbours is a
     "fingertip" (a dead end). A pixel with 1 is an isolated point;
     a pixel with 3+ is a junction or interior branch.

Returns ``(n_tips, tip_coords)`` where ``tip_coords`` is a list of
``(col, row)`` tuples.
"""
from __future__ import annotations

import numpy as np


def skeletonize(binary: np.ndarray) -> np.ndarray:
    """Skeletonise a 2D boolean mask using ``skimage.morphology.skeletonize``."""
    from skimage.morphology import skeletonize as _skel

    return _skel(binary).astype(np.uint8)


def count_tips(skeleton: np.ndarray) -> tuple[int, list[tuple[int, int]]]:
    """Count skeleton pixels whose 3x3 neighbourhood sum is exactly 2.

    A "fingertip" is a skeleton pixel with exactly 2 non-zero
    neighbours in its 3x3 neighbourhood (the pixel itself plus 1
    other).
    """
    skel = skeleton.astype(np.uint8)
    rows, cols = np.nonzero(skel)
    tips: list[tuple[int, int]] = []
    for row, col in zip(rows, cols):
        r_lo = max(row - 1, 0)
        r_hi = row + 2
        c_lo = max(col - 1, 0)
        c_hi = col + 2
        nb = skel[r_lo:r_hi, c_lo:c_hi]
        if nb.sum() == 2:
            tips.append((int(col), int(row)))
    return len(tips), tips
