"""Top-level renderer: bbox + settings in, SVG string out.

This is the single entry point used by the M1 CLI and, later, by the
/render and /export API endpoints.
"""

from __future__ import annotations

from . import dem
from .pipeline import ContourResult, Settings, extract_contours
from .svg_out import build_svg


def render_contours(
    bbox: tuple[float, float, float, float],
    settings: Settings,
    width_mm: float = 228.6,
    target_px: int = 1024,
) -> ContourResult:
    grid, _zoom = dem.dem_for_bbox(bbox, target_px=target_px)
    return extract_contours(grid, settings, width_mm=width_mm)


def render_svg(
    bbox: tuple[float, float, float, float],
    settings: Settings | None = None,
    width_mm: float = 228.6,
    line_weight_mm: float = 0.4,
    target_px: int = 1024,
) -> str:
    result = render_contours(bbox, settings or Settings(), width_mm=width_mm, target_px=target_px)
    return build_svg(result, line_weight_mm=line_weight_mm)
