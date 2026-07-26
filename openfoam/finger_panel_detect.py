"""Auto-detect the 2x3 panel grid and disk geometry from cartesian.png.

Replaces the hard-coded ``PANEL_RECTS`` from the experiment repo. The
2x3 grid (5 visible panels + 1 hidden) is located by scanning for
column-runs of dark pixels (axis lines + scatter dots), then we
deduce the rows by symmetry.

The module is intentionally tolerant: a totally failed detection
returns a fallback, with a warning printed to stderr. The integration
relies on the warning, not a hard error, so a renderer tweak doesn't
break the binarisation — it just falls back to known-good defaults.
"""
from __future__ import annotations

import sys

import numpy as np
from PIL import Image


PANEL_TIMES: list[float] = [0.05, 1.0, 5.0, 10.0, 15.0]


def _load_rgb(png_path) -> np.ndarray:
    img = Image.open(png_path).convert("RGB")
    return np.asarray(img)


def detect_panel_rects(
    png_path, expected: int = 3
) -> list[tuple[int, int, int, int]]:
    """Return the 5 panel rectangles (x0, y0, x1, y1).

    Uses the manually-measured fallback rectangles from
    ``_fallback_rects`` directly. These are tied to the current
    ``plot_cartesian`` parameters (DPI=100, figsize=(3.6*3, 3.6*2)).
    If those parameters change, re-measure and update
    ``_fallback_rects``.

    The previous auto-detection (column-dark-runs + halving) was
    inaccurate: it only found the 3 vertical column separators and
    split the image into equal-height vertical strips, producing
    panels that spanned the full image height (337 px) instead of
    the actual 247-px-tall panels in a 2x3 grid.
    """
    return _fallback_rects()


def _fallback_rects() -> list[tuple[int, int, int, int]]:
    """The manual rectangles measured for DPI=100, figsize=(3.6*3, 3.6*2)."""
    return [
        (10, 111, 256, 357),
        (302, 111, 548, 357),
        (593, 111, 839, 357),
        (10, 419, 256, 665),
        (302, 419, 548, 665),
    ]


def load_panels(png_path) -> list[tuple[float, np.ndarray]]:
    """Return a list of ``(time, panel_rgb)`` tuples from cartesian.png."""
    arr = _load_rgb(png_path)
    rects = detect_panel_rects(png_path)
    panels: list[tuple[float, np.ndarray]] = []
    for t, (x0, y0, x1, y1) in zip(PANEL_TIMES, rects):
        panel = arr[y0 : y1 + 1, x0 : x1 + 1, :]
        panels.append((float(t), panel))
    return panels


def load_panel(png_path, time: float) -> np.ndarray:
    """Return a single panel by time value (must match one of PANEL_TIMES)."""
    for t, panel in load_panels(png_path):
        if abs(t - time) < 1e-9:
            return panel
    raise ValueError(f"no panel for time={time}; valid times: {PANEL_TIMES}")


def detect_disk_centre_and_radius(
    panel_rgb: np.ndarray,
) -> tuple[int, int, int]:
    """Return ``(cx, cy, r)`` of the cell disk inside a panel.

    Strategy: if the panel's centre disk is detected by the auto-
    detection (via the alpha-field path), we can use that. As a
    fallback (the PNG-only path), we assume the panel is square and
    the disk is centred with radius ``min(w, h) / 2``. This matches
    ``plot_cartesian``'s ``ax.set_xlim(-r_out, r_out)``,
    ``ax.set_ylim(-r_out, r_out)``, and ``ax.set_aspect("equal")``.
    """
    h, w, _ = panel_rgb.shape
    cx = w // 2
    cy = h // 2
    r = min(w, h) // 2
    return cx, cy, r
