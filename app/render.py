"""Top-level renderer: bbox + settings in, SVG (or PNG) out.

Single entry point for the M1 CLI, /render (preview quality), and
/export (full quality).
"""

from __future__ import annotations

from . import dem
from .pipeline import ContourResult, Settings, extract_contours
from .svg_out import build_svg

PREVIEW_TARGET_PX = 512
EXPORT_TARGET_PX = 1024


def render_contours(
    bbox: tuple[float, float, float, float],
    settings: Settings,
    width_mm: float = 228.6,
    height_mm: float | None = None,
    target_px: int = EXPORT_TARGET_PX,
) -> ContourResult:
    grid, _zoom = dem.dem_for_bbox(bbox, target_px=target_px)
    return extract_contours(grid, settings, width_mm=width_mm, height_mm=height_mm)


def render_svg(
    bbox: tuple[float, float, float, float],
    settings: Settings | None = None,
    width_mm: float = 228.6,
    height_mm: float | None = None,
    line_weight_mm: float = 0.4,
    target_px: int = EXPORT_TARGET_PX,
) -> str:
    result = render_contours(
        bbox, settings or Settings(), width_mm=width_mm, height_mm=height_mm, target_px=target_px
    )
    return build_svg(result, line_weight_mm=line_weight_mm)


def svg_to_png(svg: str, dpi: int) -> bytes:
    """Rasterize an exported SVG at the chosen DPI.

    cairosvg reads the root element's mm dimensions, so pixel size is
    width_mm / 25.4 * dpi. Imported lazily: it needs the native cairo
    library, and the rest of the app must work without it.
    """
    import cairosvg

    return cairosvg.svg2png(bytestring=svg.encode(), dpi=dpi)
