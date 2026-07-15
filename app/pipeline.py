"""Contour quality pipeline (spec section 4).

Order is fixed: clamp ocean -> bicubic upsample -> Gaussian smooth ->
contour extraction -> Chaikin polyline smoothing -> Douglas-Peucker
simplification -> small-ring culling. Closed rings stay closed.

Coordinate flow: the DEM grid arrives in pixel space (row 0 = north).
Contours are extracted in that space, then scaled to output millimeters,
so the smoothing/simplify/culling parameters that are defined in mm act
on the physical output, independent of the selected area's size.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import contourpy
import numpy as np
from scipy import ndimage
from shapely.geometry import LineString

FT_PER_M = 1 / 0.3048


@dataclass
class Settings:
    interval: float = 40.0  # contour spacing, in `units`
    units: str = "ft"  # "ft" or "m"
    smoothing: float = 3.0  # Gaussian sigma, in source-DEM pixels
    simplify: float = 0.2  # Douglas-Peucker tolerance, output mm
    min_ring: float = 0.5  # min closed-ring area, output mm^2
    upsample: int = 3  # bicubic upsample factor (2-4)
    chaikin_iterations: int = 2


@dataclass
class ContourLevel:
    elevation: float  # in the user's units, nice round number
    lines: list[np.ndarray] = field(default_factory=list)  # (N, 2) mm coords


@dataclass
class ContourResult:
    levels: list[ContourLevel]
    width_mm: float
    height_mm: float


def prepare_grid(grid: np.ndarray, settings: Settings) -> np.ndarray:
    """Clamp ocean/bathymetry, upsample, and smooth the DEM."""
    g = np.maximum(grid, 0.0)  # terrarium includes sea-floor depths; never contour them
    factor = max(1, int(settings.upsample))
    if factor > 1:
        g = ndimage.zoom(g, factor, order=3, mode="nearest", grid_mode=True)
    if settings.smoothing > 0:
        # sigma is defined in source-DEM pixels so the slider's effect does
        # not change with the upsample factor
        g = ndimage.gaussian_filter(g, sigma=settings.smoothing * factor, mode="nearest")
    return g


def pick_levels(zmin_m: float, zmax_m: float, settings: Settings) -> list[float]:
    """Contour elevations in user units: multiples of `interval` within range.

    Levels at or below 0 are excluded — sea level is flat after clamping and
    would contour as noise along coastlines.
    """
    to_user = FT_PER_M if settings.units == "ft" else 1.0
    lo, hi = zmin_m * to_user, zmax_m * to_user
    iv = settings.interval
    first = max(math.floor(lo / iv) + 1, 1) * iv
    levels = []
    level = first
    while level < hi:
        levels.append(level)
        level += iv
    return levels


def chaikin(points: np.ndarray, iterations: int, closed: bool) -> np.ndarray:
    """Chaikin corner-cutting. Closed rings are treated cyclically and stay
    closed; open lines keep their exact endpoints."""
    pts = points[:-1] if closed and len(points) > 1 and np.allclose(points[0], points[-1]) else points
    for _ in range(iterations):
        if len(pts) < 3:
            break
        rolled = np.roll(pts, -1, axis=0) if closed else pts[1:]
        base = pts if closed else pts[:-1]
        q = base * 0.75 + rolled * 0.25
        r = base * 0.25 + rolled * 0.75
        smoothed = np.empty((len(base) * 2, 2), dtype=pts.dtype)
        smoothed[0::2] = q
        smoothed[1::2] = r
        if not closed:
            smoothed = np.vstack([pts[:1], smoothed, pts[-1:]])
        pts = smoothed
    if closed and len(pts) > 1:
        pts = np.vstack([pts, pts[:1]])
    return pts


def _is_closed(line: np.ndarray) -> bool:
    return len(line) > 3 and np.allclose(line[0], line[-1])


def _clean_line(line_mm: np.ndarray, settings: Settings) -> np.ndarray | None:
    """Chaikin-smooth, simplify, and cull one contour line (mm coordinates).

    Returns None when the line should be dropped (speckle)."""
    closed = _is_closed(line_mm)
    pts = chaikin(line_mm, settings.chaikin_iterations, closed)

    if settings.simplify > 0 and len(pts) > 2:
        simplified = LineString(pts).simplify(settings.simplify, preserve_topology=False)
        pts = np.asarray(simplified.coords)
        if closed and not np.allclose(pts[0], pts[-1]):
            pts = np.vstack([pts, pts[:1]])

    if closed:
        # shoelace area of the ring
        x, y = pts[:-1, 0], pts[:-1, 1]
        area = 0.5 * abs(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))
        if area < settings.min_ring:
            return None
    else:
        # open speckle: shorter than the perimeter of the minimum-area ring
        length = float(np.sum(np.hypot(*np.diff(pts, axis=0).T)))
        if length < 4.0 * math.sqrt(settings.min_ring):
            return None
    return pts


def extract_contours(grid: np.ndarray, settings: Settings, width_mm: float) -> ContourResult:
    """Full pipeline: prepared-DEM in, cleaned contour lines in mm out."""
    g = prepare_grid(grid, settings)
    rows, cols = g.shape
    mm_per_px = width_mm / (cols - 1) if cols > 1 else 1.0
    height_mm = (rows - 1) * mm_per_px

    to_m = 0.3048 if settings.units == "ft" else 1.0
    gen = contourpy.contour_generator(z=g, line_type=contourpy.LineType.Separate)

    result_levels = []
    for level_user in pick_levels(float(g.min()), float(g.max()), settings):
        cleaned = []
        for line in gen.lines(level_user * to_m):
            pts = _clean_line(np.asarray(line, dtype=np.float64) * mm_per_px, settings)
            if pts is not None and len(pts) >= 2:
                cleaned.append(pts)
        if cleaned:
            result_levels.append(ContourLevel(elevation=level_user, lines=cleaned))
    return ContourResult(levels=result_levels, width_mm=width_mm, height_mm=height_mm)
