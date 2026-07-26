"""Binarise a 2-D alpha field (alpha.air) or a single cartesian.png panel.

Two entry points:

- :func:`binarise_alpha_field` — operate on a 2-D ``(NPA, 4*NPZ)`` numpy
  array of alpha.air values, **independent of the renderer** (DPI,
  figsize, colormap, marker size all irrelevant).

- :func:`binarise_panel` — operate on a 3-D ``(h, w, 3)`` uint8 RGB
  panel cropped from ``cartesian.png``. The PNG path is sensitive to
  the renderer's colormap and figure size; the integration auto-detects
  the panel size and disk radius from the PNG, with a hard-coded
  fallback.

Both paths use the same :class:`BinariseParams` and the same
morphological cleanup. The alpha-field path uses a simple 0.5
threshold (with optional centre and seam masks); the PNG path uses the
HSV-saturation trick from the original ``finger-counting-experiment``.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import (
    binary_closing,
    binary_opening,
    gaussian_filter,
    generate_binary_structure,
)


@dataclass
class BinariseParams:
    saturation_threshold: float = 0.4
    red_minus_blue: float = 0.0
    blur_sigma: float = 0.5
    closing_radius: int = 2
    opening_radius: int = 0
    centre_mask_radius: int = 5
    seam_half_width_deg: float = 3.0
    disk_radius: int = 100
    apply_disk_mask: bool = True
    apply_centre_mask: bool = True
    apply_seam_mask: bool = True
    alpha_threshold: float = 0.5


def _disk_mask(h: int, w: int, cx: int, cy: int, r: int) -> np.ndarray:
    yy, xx = np.ogrid[:h, :w]
    return (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r


def _seam_mask(
    h: int, w: int, cx: int, cy: int, half_width_deg: float, r_max: int
) -> np.ndarray:
    """Mask the 4 quadrant boundaries as thin radial wedges.

    The quadrant seams in the scatter plot sit at theta = 0, pi/2, pi,
    3pi/2. We mask out pixels within ``half_width_deg`` of any of
    these angles, but only inside the disk (so we don't also mask
    background pixels). The mask is bool: True = KEEP, False = mask out.
    """
    if half_width_deg <= 0:
        return np.ones((h, w), dtype=bool)
    yy, xx = np.ogrid[:h, :w]
    dx = xx - cx
    dy = yy - cy
    r = np.sqrt(dx * dx + dy * dy)
    theta = np.degrees(np.arctan2(dy, dx))
    seam_angles = np.array([0.0, 90.0, 180.0, -90.0, -180.0])
    min_dist = np.min(
        np.abs(((theta[..., None] - seam_angles + 180) % 360) - 180), axis=-1
    )
    return ~((min_dist < half_width_deg) & (r < r_max))


def _rgb_to_saturation(rgb: np.ndarray) -> np.ndarray:
    """Convert an (h, w, 3) uint8 RGB array to HSV saturation in [0, 1]."""
    f = rgb.astype(np.float32) / 255.0
    mx = f.max(axis=-1)
    mn = f.min(axis=-1)
    with np.errstate(invalid="ignore", divide="ignore"):
        sat = np.where(mx > 0, (mx - mn) / mx, 0.0)
    return sat


def binarise_alpha_field(
    alpha: np.ndarray, params: BinariseParams | None = None
) -> np.ndarray:
    """Return a boolean ``(NPA, 4*NPZ)`` mask of "air" cells.

    The input is a 2-D numpy array of alpha.air values. Air is
    ``alpha > alpha_threshold`` (default 0.5). Centre and seam masks
    are applied in *index* space (not physical space): the cell grid
    is ``(NPA, 4*NPZ)`` and we mask the centre cell and the 4 quadrant
    seams in the polar (r, theta) layout.

    This path is **rendering-parameter independent** — the same
    algorithm works for any DPI, figsize, colormap, or marker size.
    """
    if params is None:
        params = BinariseParams()
    h, w = alpha.shape
    cx, cy = w // 2, h // 2
    r = h // 2  # NPA is the radial axis

    binary = alpha > params.alpha_threshold

    if params.apply_disk_mask:
        binary &= _disk_mask(h, w, cx, cy, r)

    if params.apply_centre_mask:
        binary &= ~_disk_mask(h, w, cx, cy, params.centre_mask_radius)

    if params.apply_seam_mask:
        binary &= _seam_mask(h, w, cx, cy, params.seam_half_width_deg, r)

    if params.closing_radius > 0:
        struct = generate_binary_structure(2, 1)
        binary = binary_closing(
            binary, structure=struct, iterations=params.closing_radius
        )
    if params.opening_radius > 0:
        struct = generate_binary_structure(2, 1)
        binary = binary_opening(
            binary, structure=struct, iterations=params.opening_radius
        )

    return binary


def binarise_panel(
    panel_rgb: np.ndarray, params: BinariseParams | None = None
) -> np.ndarray:
    """Return a boolean (h, w) mask of "air" pixels in a cartesian.png panel.

    The panel is a (h, w, 3) uint8 RGB array. The function is pure
    numpy + scipy (no skimage).
    """
    if params is None:
        params = BinariseParams()
    h, w, _ = panel_rgb.shape
    cx, cy = w // 2, h // 2
    r = params.disk_radius

    sat = _rgb_to_saturation(panel_rgb)
    if params.blur_sigma > 0:
        sat = gaussian_filter(sat, sigma=params.blur_sigma)

    f = panel_rgb.astype(np.float32) / 255.0
    red_minus_blue = f[..., 0] - f[..., 2]

    binary = (sat > params.saturation_threshold) & (
        red_minus_blue > params.red_minus_blue
    )

    if params.apply_disk_mask:
        binary &= _disk_mask(h, w, cx, cy, r)

    if params.apply_centre_mask:
        binary &= ~_disk_mask(h, w, cx, cy, params.centre_mask_radius)

    if params.apply_seam_mask:
        binary &= _seam_mask(h, w, cx, cy, params.seam_half_width_deg, r)

    if params.closing_radius > 0:
        struct = generate_binary_structure(2, 1)
        binary = binary_closing(
            binary, structure=struct, iterations=params.closing_radius
        )
    if params.opening_radius > 0:
        struct = generate_binary_structure(2, 1)
        binary = binary_opening(
            binary, structure=struct, iterations=params.opening_radius
        )

    return binary


def save_binary(binary: np.ndarray, path: str) -> None:
    """Save a boolean mask as a 0/255 PNG for visual inspection."""
    from PIL import Image

    arr = (binary.astype(np.uint8) * 255)
    Image.fromarray(arr).save(path)
