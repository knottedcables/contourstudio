"""Top-level renderer: bbox + settings in, SVG (or PNG) out.

Single entry point for the M1 CLI, /render (preview quality), and
/export (full quality). Water outlines fail soft: if Overpass is down the
render succeeds without water and a warning string is returned alongside.
"""

from __future__ import annotations

from . import dem, water as water_mod
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
    water: bool = False,
) -> tuple[ContourResult, str | None]:
    """Returns (result, warning); warning is set when water was requested
    but Overpass failed — the render itself still succeeds."""
    demgrid = dem.dem_for_bbox(bbox, target_px=target_px)
    water_px, warning = None, None
    if water:
        try:
            water_px = [
                demgrid.lonlat_to_grid_px(line)
                for line in water_mod.water_lines_cached(bbox)
            ]
        except RuntimeError as err:
            warning = str(err)
    result = extract_contours(
        demgrid.grid, settings, width_mm=width_mm, height_mm=height_mm, water_px=water_px
    )
    return result, warning


def render_svg(
    bbox: tuple[float, float, float, float],
    settings: Settings | None = None,
    width_mm: float = 228.6,
    height_mm: float | None = None,
    line_weight_mm: float = 0.4,
    target_px: int = EXPORT_TARGET_PX,
    water: bool = False,
) -> tuple[str, str | None]:
    """Returns (svg, warning) — see render_contours."""
    result, warning = render_contours(
        bbox,
        settings or Settings(),
        width_mm=width_mm,
        height_mm=height_mm,
        target_px=target_px,
        water=water,
    )
    return build_svg(result, line_weight_mm=line_weight_mm), warning


def svg_to_png(svg: str, dpi: int) -> bytes:
    """Rasterize an exported SVG at the chosen DPI.

    cairosvg reads the root element's mm dimensions, so pixel size is
    width_mm / 25.4 * dpi. Imported lazily: it needs the native cairo
    library, and the rest of the app must work without it.
    """
    import cairosvg

    return cairosvg.svg2png(bytestring=svg.encode(), dpi=dpi)
