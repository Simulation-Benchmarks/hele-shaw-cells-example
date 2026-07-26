"""Finger pipeline for the hele-shaw-cells-example benchmark.

Two paths, both producing the same metrics:

1. **Alpha-field path** (primary, used for ``solution_metrics.json``):
   operates on the 2-D ``(NPA, 4*NPZ)`` alpha.air array, **independent
   of the renderer**. Used for both the final-time metrics and the
   per-time-step ``n_fingers_over_time`` curve.

2. **PNG path** (secondary, used for the ``fingers.png`` artefact):
   operates on a panel cropped from ``cartesian.png``. Used only to
   render the visualisation, since the walkthrough embeds the image.

The PNG path is tuned for the default ``plot_cartesian`` parameters
(DPI=100, figsize=(3.6*3, 3.6*2), colormap='RdBu_r', marker size 1.0)
but is robust to small changes via auto-detection of the panel
rectangles and disk radius. If auto-detection fails, it falls back
to the hard-coded defaults and prints a warning.

Public API:

- :func:`count_fingers_from_alpha_field` — count fingertips in a
  2-D alpha field.
- :func:`critical_radius_from_alpha_field` — compute the critical
  radius (smallest distance from centre to air-region boundary) in
  metres.
- :func:`extract_finger_metrics` — end-to-end: read every time-step
  dir in a case, return the 3 new metrics for ``solution_metrics.json``.
- :func:`render_fingers_png` — render ``fingers.png`` from the
  binarised final-time panel + tip markers + critical-radius circle.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import binary_dilation

from finger_binarise import (
    BinariseParams,
    binarise_alpha_field,
    binarise_panel,
    save_binary,
)
from finger_count_tips import count_tips, skeletonize
from finger_panel_detect import (
    detect_disk_centre_and_radius,
    load_panels,
)


def _draw_tip_markers(
    base_image: np.ndarray,
    tips: list[tuple[int, int]],
    radius: int = 3,
    colour: tuple[int, int, int] = (255, 0, 0),
) -> np.ndarray:
    """Overlay filled red circles at each (x, y) tip coordinate."""
    img = base_image.copy()
    if img.ndim == 2:
        img = np.stack([img, img, img], axis=-1)
    pil = Image.fromarray(img)
    draw = ImageDraw.Draw(pil)
    for (x, y) in tips:
        draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            fill=colour,
            outline=colour,
        )
    return np.asarray(pil)


def _critical_radius_px(
    binary: np.ndarray, cx: int, cy: int
) -> int | None:
    """Compute the critical radius (smallest distance from centre to
    the air region's boundary) in pixel units.

    The boundary is the set of *air* cells that have a non-air
    4-neighbour. For a filled disc, this is the outer ring (one cell
    thick). For a non-filled region (e.g. fingers around a centre
    disc), this is the cells at the air-soap interface.
    """
    h, w = binary.shape
    air = binary.astype(bool)
    not_air = ~air
    boundary = np.zeros_like(air)
    boundary[1:-1, :] |= not_air[0:-2, :]
    boundary[1:-1, :] |= not_air[2:, :]
    boundary[:, 1:-1] |= not_air[:, 0:-2]
    boundary[:, 1:-1] |= not_air[:, 2:]
    boundary &= air
    if not boundary.any():
        return None
    rows, cols = np.nonzero(boundary)
    dists = np.sqrt((rows - cy) ** 2 + (cols - cx) ** 2)
    return int(round(dists.min()))


def _r_phys_from_px(
    r_px: int | None, disk_radius_px: int, r_out_m: float
) -> float | None:
    """Convert a radius in pixel units to physical metres."""
    if r_px is None or disk_radius_px <= 0:
        return None
    return r_px * r_out_m / disk_radius_px


def count_fingers_from_alpha_field(
    alpha: np.ndarray,
    params: BinariseParams | None = None,
) -> tuple[int, np.ndarray, np.ndarray, list[tuple[int, int]]]:
    """Count fingers in a 2-D ``(NPA, 4*NPZ)`` alpha.air field.

    Returns ``(n_fingers, binary, skeleton, tip_coords)`` where
    ``tip_coords`` is a list of ``(col, row)`` indices in the
    binarised mask.
    """
    binary = binarise_alpha_field(alpha, params)
    skel = skeletonize(binary)
    n_tips, tips = count_tips(skel)
    return n_tips, binary, skel, tips


def critical_radius_from_alpha_field(
    alpha: np.ndarray,
    r_out_m: float,
    params: BinariseParams | None = None,
) -> tuple[float | None, int | None, np.ndarray, list[tuple[int, int]]]:
    """Compute the critical radius (in metres) for a 2-D alpha field.

    The disk radius in cells is ``NPA // 2`` (the radial axis runs
    from 0 to NPA/2 cells of the physical disk). Returns
    ``(r_crit_m, r_crit_px, binary, tips)``.

    For the alpha-field path, the ``cx, cy`` of the binarised mask is
    the centre of the ``(NPA, 4*NPZ)`` grid; the disk radius in cells
    is ``NPA // 2`` (so we don't need the auto-detected panel size).
    """
    binary = binarise_alpha_field(alpha, params)
    h, w = binary.shape
    cx, cy = w // 2, h // 2
    disk_radius_cells = h // 2
    r_crit_px = _critical_radius_px(binary, cx, cy)
    r_crit_m = _r_phys_from_px(r_crit_px, disk_radius_cells, r_out_m)
    skel = skeletonize(binary)
    _, tips = count_tips(skel)
    return r_crit_m, r_crit_px, binary, tips


# ---------------------------------------------------------------------------
# Alpha-field path: read OF time-step dirs
# ---------------------------------------------------------------------------

_HEADER_RE = re.compile(
    r"internalField\s+nonuniform\s+List<scalar>\s+(\d+)\s*\(([^)]*)\)\s*;",
    re.DOTALL,
)
_UNIFORM_RE = re.compile(
    r"internalField\s+uniform\s+(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*;"
)


def _read_alpha_air(path: Path) -> np.ndarray | None:
    """Read an OF ``alpha.air`` volScalarField and return the raw 1-D
    float array. Returns ``None`` if the file is missing, uniform, or
    unparseable.
    """
    if not path.exists():
        return None
    text = path.read_text(errors="replace")
    m_uni = _UNIFORM_RE.search(text)
    if m_uni:
        return None
    m = _HEADER_RE.search(text)
    if not m:
        return None
    n = int(m.group(1))
    floats = [float(tok) for tok in m.group(2).split()]
    if len(floats) != n:
        return None
    return np.asarray(floats, dtype=float)


def _alpha_air_to_2d(
    alpha_flat: np.ndarray, npa: int, npz: int
) -> np.ndarray:
    """Reshape a flat OF alpha.air array to ``(NPA, 4*NPZ)``.

    OF writes 4 quadrants x (NPA radial x NPZ angular) cells. We
    stack the 4 quadrants angularly.
    """
    if alpha_flat.size == 4 * npa * npz:
        arr_3d = alpha_flat.reshape((4, npz, npa))  # (q, theta, r)
        return arr_3d.transpose(0, 2, 1).reshape((npa, 4 * npz))
    if alpha_flat.size == npa * npz:
        return alpha_flat.reshape((npa, npz))
    raise ValueError(
        f"unexpected alpha.air size: {alpha_flat.size} "
        f"(expected {npa * npz} or {4 * npa * npz})"
    )


def extract_finger_metrics(
    case_dir: Path,
    params: BinariseParams | None = None,
    parameters: dict | None = None,
) -> dict[str, Any]:
    """Compute the 3 new finger metrics from a finished run.

    Returns a dict with keys:

    - ``final_number_of_fingers`` (int): fingertips in the binarised
      air region at the last time-step.
    - ``critical_radius_m`` (float | None): smallest distance from the
      cell centre to the air-region boundary at the last time-step,
      in metres.
    - ``n_fingers_over_time`` (dict[str, int]): mapping time-step
      string (e.g. ``"0.05"``) -> finger count.

    The ``parameters`` dict must contain ``domain.R_out``,
    ``mesh.NPA``, ``mesh.NPZ``. If ``None``, the function tries to
    load ``parameters_<config>.json`` from one or two levels up.
    """
    case_dir = Path(case_dir)
    if params is None:
        params = BinariseParams()
    if parameters is None:
        parameters = _load_parameters(case_dir)

    r_out = float(parameters["domain"]["R_out"])
    npa = int(parameters["mesh"]["NPA"])
    npz = int(parameters["mesh"]["NPZ"])

    n_fingers_over_time: dict[str, int] = {}
    final_n: int | None = None
    final_r_m: float | None = None

    timesteps_dir = case_dir / "Timesteps"
    if not timesteps_dir.is_dir():
        return {
            "final_number_of_fingers": None,
            "critical_radius_m": None,
            "n_fingers_over_time": {},
        }

    for entry in sorted(timesteps_dir.iterdir(), key=lambda e: e.name):
        if not entry.is_dir():
            continue
        try:
            float(entry.name)
        except ValueError:
            continue
        alpha_path = entry / "alpha.air"
        flat = _read_alpha_air(alpha_path)
        if flat is None:
            continue
        try:
            alpha_2d = _alpha_air_to_2d(flat, npa, npz)
        except ValueError as exc:
            print(
                f"finger_pipeline: WARN: {exc}; skipping {entry.name}",
                file=sys.stderr,
            )
            continue
        n, _binary, _skel, _tips = count_fingers_from_alpha_field(
            alpha_2d, params
        )
        # Normalise the time-step key: prefer the int form when
        # possible (e.g. "15" instead of "15.0"). The walkthrough
        # notebook and tests/compare.py expect "0.05" / "1" / "5" /
        # "10" / "15" not "0.05" / "1.0" / "5.0" / ...
        try:
            t_float = float(entry.name)
            if t_float == int(t_float):
                key = str(int(t_float))
            else:
                key = entry.name
        except ValueError:
            key = entry.name
        n_fingers_over_time[key] = n

    # Find the latest time-step dir on disk (which may be "15.0"
    # while the normalised key in n_fingers_over_time is "15"). We
    # use the same normalisation for matching.
    last_time = max(
        (t for t in n_fingers_over_time.keys()),
        key=lambda s: float(s),
        default=None,
    )
    if last_time is not None:
        # Look up the actual on-disk dir by float match.
        target_t = float(last_time)
        on_disk_dir = None
        for entry in timesteps_dir.iterdir():
            if not entry.is_dir():
                continue
            try:
                if float(entry.name) == target_t:
                    on_disk_dir = entry
                    break
            except ValueError:
                continue
        if on_disk_dir is not None:
            alpha_path = on_disk_dir / "alpha.air"
            flat = _read_alpha_air(alpha_path)
            if flat is not None:
                alpha_2d = _alpha_air_to_2d(flat, npa, npz)
                r_crit_m, _r_crit_px, _binary, _tips = (
                    critical_radius_from_alpha_field(alpha_2d, r_out, params)
                )
                final_n = n_fingers_over_time[last_time]
                final_r_m = r_crit_m

    return {
        "final_number_of_fingers": final_n,
        "critical_radius_m": final_r_m,
        "n_fingers_over_time": n_fingers_over_time,
    }


def _load_parameters(case_dir: Path) -> dict:
    """Locate the parameters_<config>.json for a case_dir.

    Search order:
      1. ``<case_dir>/../parameters_<config>.json``
      2. ``<case_dir>/../parameters.json``
      3. ``<case_dir>/../../parameters_<config>.json``
      4. ``<case_dir>/../../parameters.json``

    Raises ``FileNotFoundError`` if none is found.
    """
    case_dir = Path(case_dir).resolve()
    leaf = case_dir.name
    parent = case_dir.parent
    grandparent = parent.parent
    candidates = [
        parent / f"parameters_{leaf}.json",
        parent / "parameters.json",
        grandparent / f"parameters_{leaf}.json",
        grandparent / "parameters.json",
    ]
    for c in candidates:
        if c.exists():
            return json.loads(c.read_text())
    raise FileNotFoundError(
        f"could not locate parameters JSON for {case_dir}; tried: "
        + ", ".join(str(c) for c in candidates)
    )


# ---------------------------------------------------------------------------
# PNG path: render fingers.png from cartesian.png
# ---------------------------------------------------------------------------


def render_fingers_png(
    case_dir: Path,
    cartesian_png: Path,
    output_png: Path,
    parameters: dict | None = None,
    params: BinariseParams | None = None,
    time: float = 15.0,
) -> dict:
    """Render the final-frame visualisation: binarised panel + red tip
    markers + red circle at the critical radius.

    Returns a dict with the computed metrics for this frame.
    """
    if params is None:
        params = BinariseParams()
    if parameters is None:
        parameters = _load_parameters(case_dir)
    r_out = float(parameters["domain"]["R_out"])

    from finger_panel_detect import load_panel

    panel = load_panel(cartesian_png, time)

    # The disk radius in pixels is exactly half the smaller panel
    # dimension (plot_cartesian uses aspect='equal' and
    # set_xlim/set_ylim = +/- r_out). The hard-coded
    # ``BinariseParams.disk_radius = 100`` was tuned for the
    # experiment's PDF render and doesn't match the current
    # cartesian.png layout. Use the panel-derived value, but keep the
    # other BinariseParams fields (saturation, blur, masks) from the
    # caller. If the panel-derived radius differs from the caller's
    # hard-coded value, log a warning — this is the intended
    # robustness signal for a renderer change.
    cx, cy, panel_radius_px = detect_disk_centre_and_radius(panel)
    panel_params = BinariseParams(
        saturation_threshold=params.saturation_threshold,
        red_minus_blue=params.red_minus_blue,
        blur_sigma=params.blur_sigma,
        closing_radius=params.closing_radius,
        opening_radius=params.opening_radius,
        centre_mask_radius=params.centre_mask_radius,
        seam_half_width_deg=params.seam_half_width_deg,
        disk_radius=panel_radius_px,
        apply_disk_mask=params.apply_disk_mask,
        apply_centre_mask=params.apply_centre_mask,
        apply_seam_mask=params.apply_seam_mask,
    )
    if abs(panel_radius_px - params.disk_radius) > 0.20 * max(
        params.disk_radius, 1
    ):
        print(
            f"finger_pipeline: WARN: panel-derived disk radius "
            f"{panel_radius_px} differs from BinariseParams.disk_radius "
            f"{params.disk_radius} by >= 20%; using the panel-derived "
            f"value. This is expected if plot_cartesian's DPI/figsize "
            f"has changed since the params were tuned.",
            file=sys.stderr,
        )

    binary = binarise_panel(panel, panel_params)
    skel = skeletonize(binary)
    n_tips, tips = count_tips(skel)

    disk_radius_px = panel_radius_px
    r_crit_px = _critical_radius_px(binary, cx, cy)
    r_crit_m = _r_phys_from_px(r_crit_px, disk_radius_px, r_out)

    binary_rgb = (
        np.stack([binary, binary, binary], axis=-1).astype(np.uint8) * 255
    )
    overlay = _draw_tip_markers(binary_rgb, tips)

    if r_crit_px is not None and r_crit_px > 0:
        pil = Image.fromarray(overlay)
        draw = ImageDraw.Draw(pil)
        draw.ellipse(
            (cx - r_crit_px, cy - r_crit_px, cx + r_crit_px, cy + r_crit_px),
            outline=(255, 0, 0),
            width=1,
        )
        overlay = np.asarray(pil)

    output_png = Path(output_png)
    output_png.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(overlay).save(output_png)
    print(f"finger_pipeline: wrote {output_png}")

    return {
        "time": time,
        "n_fingers": n_tips,
        "critical_radius_px": r_crit_px,
        "critical_radius_m": r_crit_m,
        "disk_radius_px_used": disk_radius_px,
        "output_path": str(output_png),
    }


# ---------------------------------------------------------------------------
# Legacy helpers (kept for back-compat with the experiment repo API)
# ---------------------------------------------------------------------------


def run_pipeline(
    png_path: str | Path,
    params: BinariseParams | None = None,
    output_dir: str | Path | None = None,
    r_out_m: float = 0.095,
) -> list[dict]:
    """Legacy: run the full pipeline on the 5-panel cartesian.png.

    Returns a list of dicts (one per time-point) with keys:
      time, n_fingers, n_tip_coords, n_skel_pixels, n_binary_pixels,
      critical_radius_px, critical_radius_m.
    """
    if params is None:
        params = BinariseParams()
    panels = load_panels(png_path)
    results: list[dict] = []
    if output_dir is not None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    for t, panel in panels:
        binary = binarise_panel(panel, params)
        skel = skeletonize(binary)
        n_tips, tips = count_tips(skel)
        h, w = binary.shape
        cx, cy = w // 2, h // 2
        r_crit_px = _critical_radius_px(binary, cx, cy)
        r_crit_m = _r_phys_from_px(r_crit_px, params.disk_radius, r_out_m)
        result = {
            "time": t,
            "n_fingers": n_tips,
            "n_tip_coords": len(tips),
            "n_skel_pixels": int(skel.sum()),
            "n_binary_pixels": int(binary.sum()),
            "critical_radius_px": r_crit_px,
            "critical_radius_m": r_crit_m,
        }
        results.append(result)
        if output_dir is not None:
            t_str = f"t{t:05.2f}".replace(".", "_")
            save_binary(binary, output_dir / f"{t_str}_binarised.png")
            binary_rgb = (
                np.stack([binary, binary, binary], axis=-1).astype(np.uint8)
                * 255
            )
            overlay = _draw_tip_markers(binary_rgb, tips)
            Image.fromarray(overlay).save(output_dir / f"{t_str}_tips.png")
            original_with_tips = _draw_tip_markers(panel, tips)
            Image.fromarray(original_with_tips).save(
                output_dir / f"{t_str}_skeleton.png"
            )
    return results


def write_results_json(
    results: list[dict], params: BinariseParams, path: str | Path
) -> None:
    out = {
        "params": asdict(params),
        "tips_per_time": {f"{r['time']:g}": r["n_fingers"] for r in results},
        "details": results,
    }
    Path(path).write_text(json.dumps(out, indent=2))


def plot_tips_per_time(
    results: list[dict], path: str | Path, title: str = "config"
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    times = [r["time"] for r in results]
    n_tips = [r["n_fingers"] for r in results]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.scatter(times, n_tips, c="r", s=100, zorder=3, label="actual panels")
    ax.set_xlabel("TIME t in s")
    ax.set_ylabel("NUMBER OF FINGERS")
    ax.set_title(f"Number of fingers over time ({title})")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=125)
    plt.close(fig)
