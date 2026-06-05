#!/usr/bin/env python3
"""openfoam/plot_fingers.py — radial fingering visualization for a finished run.

Reads the post-run ``alpha.air`` volScalarField at user-chosen times and
produces a multi-panel PNG (or PDF) figure showing the radial fingering
pattern. Blue = soap (alpha.air = 0), red = air (alpha.air = 1).

Run from the repo root, e.g.::

    python openfoam/plot_fingers.py --results-dir results/1 \\
        --times 0.05 1 5 10 15 \\
        --output results/1/fingers.png

The script is pure stdlib + numpy + matplotlib (Agg backend for headless
rendering). It imports ``parse_alpha_field`` from the sibling
``openfoam/metrics.py`` for the OF ASCII field parser, falling back to
the same regex locally if the import is not available.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Reuse the OF volScalarField parser from openfoam/metrics.py if we can.
try:
    from metrics import parse_alpha_field  # type: ignore
except Exception:  # noqa: BLE001
    parse_alpha_field = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

_HEADER_RE = re.compile(
    r"internalField\s+nonuniform\s+List<scalar>\s+(\d+)\s*\(([^)]*)\)\s*;",
    re.DOTALL,
)
_UNIFORM_RE = re.compile(
    r"internalField\s+uniform\s+(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*;",
)


def _parse_alpha_local(path: Path) -> tuple[bool, np.ndarray | float]:
    """Parse an OF volScalarField ASCII file.

    Returns ``(is_uniform, value)`` where ``value`` is either a float
    (uniform) or a 1-D numpy array (non-uniform). Raises ``ValueError``
    on parse failure.
    """
    text = Path(path).read_text(errors="replace")
    m = _UNIFORM_RE.search(text)
    if m:
        return True, float(m.group(1))
    m = _HEADER_RE.search(text)
    if not m:
        raise ValueError(f"could not parse internalField in {path}")
    n = int(m.group(1))
    floats = [float(tok) for tok in m.group(2).split()]
    if len(floats) != n:
        raise ValueError(
            f"header says {n} entries, parsed {len(floats)} in {path}"
        )
    return False, np.asarray(floats, dtype=float)


def read_alpha_field(path: Path, npa: int, npz: int) -> np.ndarray:
    """Read ``<time>/alpha.air`` and return a 2-D ``(NPA, NPZ)`` array.

    Falls back to zeros if the file is uniform or unparseable, so the
    panel still renders (with a warning).
    """
    try:
        # Prefer the metrics.py parser if importable — same regex, but
        # we still get the uniform case handled consistently.
        if parse_alpha_field is not None:
            stats = parse_alpha_field(Path(path))
            if stats is not None and stats.get("n_cells") == npa * npz:
                # Need the raw values, which metrics.py doesn't return.
                # Fall through to local parser.
                pass
        is_uniform, value = _parse_alpha_local(Path(path))
    except (FileNotFoundError, ValueError) as exc:
        print(f"plot_fingers: WARN: {exc}; substituting zeros", file=sys.stderr)
        return np.zeros((npa, npz), dtype=float)

    if is_uniform:
        print(
            f"plot_fingers: WARN: {path} is a uniform field "
            f"(value={value}); substituting zeros for plotting",
            file=sys.stderr,
        )
        return np.zeros((npa, npz), dtype=float)

    arr = np.asarray(value, dtype=float)
    if arr.size == 4 * npa * npz:
        # OF writes 4 quadrants × (NPA radial × NPZ angular) cells.
        # The flat index is (q, theta, r) — verified empirically: with
        # the post-setFields cylinder (240 ones at r=0 in the 1-cell-thick
        # innermost ring), arr.reshape(4, npz, npa)[0, :5, 0] == 1.
        # Stack 4 quadrants angularly → (r, 4*theta) for pcolormesh
        # (the .T transpose in the pcolormesh call swaps to (4*theta, r)).
        arr_3d = arr.reshape((4, npz, npa))   # (q, theta, r)
        return arr_3d.transpose(0, 2, 1).reshape((npa, 4 * npz))  # (r, 4*theta)
    if arr.size == npa * npz:
        return arr.reshape((npa, npz))
    print(
        f"plot_fingers: WARN: {path} has {arr.size} cells, expected "
        f"{npa * npz} (single quadrant) or {4 * npa * npz} (4 quadrants); "
        f"substituting zeros",
        file=sys.stderr,
    )
    return np.zeros((npa, npz), dtype=float)


# ---------------------------------------------------------------------------
# Parameters lookup
# ---------------------------------------------------------------------------

def resolve_parameters_file(
    results_dir: Path,
    explicit: str | None,
) -> Path:
    """Locate the parameters JSON for this run.

    Search order:
      1. explicit ``--parameters-file`` argument
      2. ``<results-dir>/../parameters_<config>.json`` (one level up)
      3. ``<results-dir>/../parameters.json`` (one level up)
      4. ``<results-dir>/../../parameters_<config>.json`` (two levels up)
      5. ``<results-dir>/../../parameters.json`` (two levels up)

    The "one level up" form supports layouts like ``sim/1/`` →
    ``sim/parameters_1.json``; the "two levels up" form supports the
    layout used in this repo (``results/<config>/`` with parameters at
    the repo root).
    """
    if explicit:
        p = Path(explicit)
        if not p.exists():
            print(
                f"plot_fingers: ERROR: parameters file not found: {p}",
                file=sys.stderr,
            )
            sys.exit(2)
        return p

    parent = results_dir.parent
    grandparent = parent.parent
    leaf = results_dir.name
    candidates = [
        parent / f"parameters_{leaf}.json",
        parent / "parameters.json",
        grandparent / f"parameters_{leaf}.json",
        grandparent / "parameters.json",
    ]
    for c in candidates:
        if c.exists():
            return c

    print(
        "plot_fingers: ERROR: could not locate parameters JSON. Tried:\n  "
        + "\n  ".join(str(c) for c in candidates)
        + "\nPass --parameters-file explicitly.",
        file=sys.stderr,
    )
    sys.exit(2)


def load_parameters(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def _grid_layout(n: int) -> tuple[int, int]:
    """Return ``(nrows, ncols)`` for an n-panel polar figure."""
    if n <= 0:
        return 1, 1
    if n == 1:
        return 1, 1
    if n == 2:
        return 1, 2
    if n == 3:
        return 1, 3
    if n == 4:
        return 2, 2
    if n <= 6:
        return 2, 3
    if n <= 9:
        return 3, 3
    cols = 3
    rows = (n + cols - 1) // cols
    return rows, cols


def plot_fingers(
    results_dir: Path,
    times: list[float],
    output: Path,
    params: dict,
    colormap: str,
    dpi: int,
) -> None:
    domain = params.get("domain", {})
    mesh = params.get("mesh", {})
    r_in = float(domain["R_in"])
    r_out = float(domain["R_out"])
    npa = int(mesh["NPA"])
    npz = int(mesh["NPZ"])

    dr = (r_out - r_in) / npa
    # 4 quadrants tiled angularly → 4*NPZ angular bins total.
    dth = 2.0 * np.pi / (4 * npz)
    r_edges = np.linspace(r_in, r_out, npa + 1)
    r_centers = r_edges[:-1] + 0.5 * dr
    th_edges = np.linspace(0.0, 2.0 * np.pi, 4 * npz + 1)
    th_centers = th_edges[:-1] + 0.5 * dth

    times_present: list[tuple[float, np.ndarray]] = []
    for t in times:
        alpha_path = results_dir / f"{t}" / "alpha.air"
        if not alpha_path.exists():
            # OF writes times as e.g. "1e-05" or "0.05"; try a couple of
            # common spellings before giving up.
            alt_candidates = []
            try:
                alt_candidates.append(results_dir / f"{t:g}" / "alpha.air")
                alt_candidates.append(results_dir / f"{t:.6g}" / "alpha.air")
            except Exception:
                pass
            if any(p.exists() for p in alt_candidates):
                alpha_path = next(p for p in alt_candidates if p.exists())
            else:
                print(
                    f"plot_fingers: WARN: no alpha.air at t={t} "
                    f"(looked for {alpha_path}); skipping",
                    file=sys.stderr,
                )
                continue
        field = read_alpha_field(alpha_path, npa, npz)
        times_present.append((float(t), field))

    if not times_present:
        print(
            "plot_fingers: ERROR: no requested times were present in "
            f"{results_dir}; nothing to plot",
            file=sys.stderr,
        )
        sys.exit(2)

    n = len(times_present)
    nrows, ncols = _grid_layout(n)
    fig, axes = plt.subplots(
        nrows, ncols,
        subplot_kw={"projection": "polar"},
        figsize=(3.6 * ncols, 3.6 * nrows),
    )
    axes = np.atleast_1d(axes).ravel()

    vmin, vmax = 0.0, 1.0
    images = []
    for ax, (t, field) in zip(axes, times_present):
        # field is (NPA, 4*NPZ) for the 4-quadrant case (or (NPA, NPZ)
        # for the single-quadrant case). pcolormesh with shading="nearest"
        # wants C of shape (Ny, Nx) where X=th_centers (Nx values) and
        # Y=r_centers (Ny values) — i.e. C must be (npa, 4*npz). We pass
        # the field as-is; the .T would be a no-op visually but would
        # raise a shape-mismatch error from matplotlib.
        mesh_artist = ax.pcolormesh(
            th_centers, r_centers, field, cmap=colormap,
            vmin=vmin, vmax=vmax, shading="nearest",
        )
        images.append(mesh_artist)
        ax.set_title(f"t = {t:g} s", fontsize=10)
        ax.set_yticklabels([])
        ax.set_xticklabels([])
        ax.set_ylim(r_in, r_out)
        ax.set_theta_zero_location("E")
        ax.set_theta_direction(1)

    # Hide any unused axes
    for ax in axes[n:]:
        ax.set_visible(False)

    # One shared colorbar for the whole figure
    cbar = fig.colorbar(
        images[0], ax=axes[:n].tolist(),
        orientation="vertical", fraction=0.025, pad=0.02,
    )
    cbar.set_label(r"$\alpha_{\mathrm{air}}$  (0 = soap, 1 = air)")

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.suptitle(
        f"Radial fingering — {results_dir.name}", fontsize=12, y=1.02
    )
    # fig.tight_layout() is not reliable with polar axes, so we just
    # use subplots_adjust and let bbox_inches='tight' trim whitespace.
    fig.subplots_adjust(wspace=0.25, hspace=0.35, right=0.9)
    fig.savefig(output, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(
        f"plot_fingers: wrote {output} "
        f"({n}/{len(times)} times, layout {nrows}x{ncols})"
    )


# ---------------------------------------------------------------------------
# Cartesian (X-Y) plotting
# ---------------------------------------------------------------------------

def _read_alpha_4quadrant_clean(path: Path) -> tuple[int, np.ndarray] | None:
    """Read an OF volScalarField and return (cells_per_quadrant, arr_3d).

    The returned ``arr_3d`` has shape ``(4, cells_per_quadrant)`` where
    cells are in (q, theta, r) order. Returns ``None`` if the field is
    uniform or unparseable.
    """
    try:
        text = Path(path).read_text(errors="replace")
    except FileNotFoundError:
        return None
    m_uni = _UNIFORM_RE.search(text)
    if m_uni:
        return None
    m = _HEADER_RE.search(text)
    if not m:
        return None
    n = int(m.group(1))
    if n % 4 != 0:
        return None
    floats = [float(tok) for tok in m.group(2).split()]
    if len(floats) != n:
        return None
    return (n // 4, np.asarray(floats, dtype=float).reshape((4, n // 4)))


def plot_cartesian(
    results_dir: Path,
    times: list[float],
    output: Path,
    params: dict,
    colormap: str,
    dpi: int,
) -> None:
    """5-panel Cartesian (X-Y) plot of the radial fingering.

    For each requested time, renders the alpha.air field as a 2D X-Y
    scatter plot, where each cell is plotted at its physical (x, y)
    position derived from polar (r, theta). The 4 mesh quadrants are
    tiled angularly around the centre, producing the classic
    "viscous fingering" / "alien-like" dendritic pattern.

    The figure is a 2x3 grid (5 panels + 1 hidden) with one time per
    panel. Colour: ``alpha.air`` from 0 (soap, blue) to 1 (air, red).
    """
    domain = params.get("domain", {})
    mesh = params.get("mesh", {})
    r_in = float(domain["R_in"])
    r_out = float(domain["R_out"])
    npa = int(mesh["NPA"])
    npz = int(mesh["NPZ"])

    dr = (r_out - r_in) / npa
    r_centers = r_in + (np.arange(npa) + 0.5) * dr
    dth_local = (np.pi / 2) / npz

    # Pre-compute the (x, y) cell centres for each of the 4 quadrants.
    # Quadrant q covers angular range [q*pi/2, (q+1)*pi/2].
    quad_xy: list[tuple[np.ndarray, np.ndarray]] = []
    for q in range(4):
        th_centers = q * (np.pi / 2) + (np.arange(npz) + 0.5) * dth_local
        R, TH = np.meshgrid(r_centers, th_centers, indexing="ij")
        quad_xy.append((R.ravel(), TH.ravel()))

    times_present: list[tuple[float, np.ndarray, np.ndarray, np.ndarray]] = []
    for t in times:
        alpha_path = results_dir / f"{t}" / "alpha.air"
        if not alpha_path.exists():
            alt_candidates = []
            try:
                alt_candidates.append(results_dir / f"{t:g}" / "alpha.air")
                alt_candidates.append(results_dir / f"{t:.6g}" / "alpha.air")
            except Exception:
                pass
            if any(p.exists() for p in alt_candidates):
                alpha_path = next(p for p in alt_candidates if p.exists())
            else:
                print(
                    f"plot_cartesian: WARN: no alpha.air at t={t} "
                    f"(looked for {alpha_path}); substituting zeros",
                    file=sys.stderr,
                )
                # Use a uniform-zero field so the panel still renders.
                n_total = 4 * npa * npz
                Xs = np.concatenate([xy[0] for xy in quad_xy])
                Ys = np.concatenate([xy[1] for xy in quad_xy])
                As = np.zeros(n_total, dtype=float)
                times_present.append((float(t), Xs, Ys, As))
                continue

        result = _read_alpha_4quadrant_clean(alpha_path)
        if result is None:
            print(
                f"plot_cartesian: WARN: {alpha_path} is uniform or "
                f"unparseable; substituting zeros",
                file=sys.stderr,
            )
            n_total = 4 * npa * npz
            Xs = np.concatenate([xy[0] for xy in quad_xy])
            Ys = np.concatenate([xy[1] for xy in quad_xy])
            As = np.zeros(n_total, dtype=float)
            times_present.append((float(t), Xs, Ys, As))
            continue

        cells_per_q, arr_3d = result
        if cells_per_q != npa * npz:
            print(
                f"plot_cartesian: WARN: {alpha_path} has "
                f"{cells_per_q} cells per quadrant, expected {npa * npz} "
                f"(NPA*NPZ); substituting zeros",
                file=sys.stderr,
            )
            n_total = 4 * npa * npz
            Xs = np.concatenate([xy[0] for xy in quad_xy])
            Ys = np.concatenate([xy[1] for xy in quad_xy])
            As = np.zeros(n_total, dtype=float)
            times_present.append((float(t), Xs, Ys, As))
            continue

        # arr_3d shape (4, npa*npz) is in (q, theta*r) order. Reshape
        # each quadrant to (npz, npa) = (theta, r) and ravel — this
        # matches the (R, TH) meshgrid we built in quad_xy.
        Xs_list, Ys_list, As_list = [], [], []
        for q in range(4):
            R_q, TH_q = quad_xy[q]
            A_q = arr_3d[q].reshape((npz, npa)).T.ravel()  # (theta, r) → (r, theta)
            Xs_list.append(R_q * np.cos(TH_q))
            Ys_list.append(R_q * np.sin(TH_q))
            As_list.append(A_q)
        times_present.append((
            float(t),
            np.concatenate(Xs_list),
            np.concatenate(Ys_list),
            np.concatenate(As_list),
        ))

    if not times_present:
        print(
            "plot_cartesian: ERROR: no requested times were present in "
            f"{results_dir}; nothing to plot",
            file=sys.stderr,
        )
        sys.exit(2)

    n = len(times_present)
    nrows, ncols = _grid_layout(n)
    fig, axes = plt.subplots(
        nrows, ncols,
        figsize=(3.6 * ncols, 3.6 * nrows),
        subplot_kw={"aspect": "equal"},
    )
    axes = np.atleast_1d(axes).ravel()

    vmin, vmax = 0.0, 1.0
    for ax, (t, Xs, Ys, As) in zip(axes, times_present):
        # Use a square marker whose size in points is small enough that
        # neighbouring cells touch but doesn't overpower the figure.
        # With ~14400 cells, a marker size of ~1 pt gives a clean look
        # at 100 DPI for an 11×7 inch figure.
        ax.scatter(
            Xs, Ys, c=As, cmap=colormap,
            vmin=vmin, vmax=vmax, s=1.0, marker="s", linewidths=0,
            rasterized=True,
        )
        ax.set_title(f"t = {t:g} s", fontsize=10)
        ax.set_xlim(-r_out, r_out)
        ax.set_ylim(-r_out, r_out)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_aspect("equal")

    # Hide any unused axes
    for ax in axes[n:]:
        ax.set_visible(False)

    # One shared colorbar for the whole figure
    sm = plt.cm.ScalarMappable(cmap=colormap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
    sm.set_array([])
    cbar = fig.colorbar(
        sm, ax=axes[:n].tolist(),
        orientation="vertical", fraction=0.025, pad=0.02,
    )
    cbar.set_label(r"$\alpha_{\mathrm{air}}$  (0 = soap, 1 = air)")

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.suptitle(
        f"Viscous fingering (Cartesian) — {results_dir.name}", fontsize=12, y=1.02
    )
    fig.subplots_adjust(wspace=0.15, hspace=0.25, right=0.9)
    fig.savefig(output, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(
        f"plot_cartesian: wrote {output} "
        f"({n}/{len(times)} times, layout {nrows}x{ncols})"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--results-dir", type=Path, required=True,
        help="Working case dir (e.g. results/1)",
    )
    ap.add_argument(
        "--times", type=float, nargs="+", required=True,
        help="Simulation times to render (floats). Missing times are "
             "skipped with a warning.",
    )
    ap.add_argument(
        "--output", type=Path, required=True,
        help="Path to the output figure (PNG or PDF inferred from suffix)",
    )
    ap.add_argument(
        "--parameters-file", type=str, default=None,
        help="Path to the parameters JSON. If omitted, looks for "
             "<results-dir>/../parameters_<config>.json",
    )
    ap.add_argument(
        "--colormap", type=str, default="RdBu_r",
        help="Matplotlib colormap (default: RdBu_r; blue=soap, red=air)",
    )
    ap.add_argument(
        "--dpi", type=int, default=100,
        help="Figure DPI (default: 100)",
    )
    ap.add_argument(
        "--cartesian", action="store_true",
        help="Generate a Cartesian (X-Y) plot of the radial fingering "
             "instead of the default polar (r, theta) plot. Each cell "
             "is plotted at its physical (x, y) position derived from "
             "polar (r, theta), with the 4 mesh quadrants tiled around "
             "the centre — produces the classic 'viscous fingering' / "
             "'alien-like' dendritic pattern.",
    )
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    results_dir = Path(args.results_dir)
    if not results_dir.is_dir():
        print(
            f"plot_fingers: ERROR: results dir not found: {results_dir}",
            file=sys.stderr,
        )
        return 2

    params_path = resolve_parameters_file(
        results_dir, args.parameters_file
    )
    params = load_parameters(params_path)

    if args.cartesian:
        plot_cartesian(
            results_dir=results_dir,
            times=list(args.times),
            output=Path(args.output),
            params=params,
            colormap=args.colormap,
            dpi=args.dpi,
        )
    else:
        plot_fingers(
            results_dir=results_dir,
            times=list(args.times),
            output=Path(args.output),
            params=params,
            colormap=args.colormap,
            dpi=args.dpi,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
