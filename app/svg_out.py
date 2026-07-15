"""SVG output (spec section 7).

Physical mm dimensions on the root element, viewBox in the same mm units so
1 user unit = 1 mm, fill="none", stroke="black", one <path> per contour ring,
grouped by elevation level in <g data-elevation="..."> for per-level
selection in Inkscape/LightBurn.
"""

from __future__ import annotations

import numpy as np

from .pipeline import ContourResult


def _path_d(points: np.ndarray) -> str:
    closed = len(points) > 3 and np.allclose(points[0], points[-1])
    pts = points[:-1] if closed else points
    coords = " L ".join(f"{x:.2f} {y:.2f}" for x, y in pts)
    return f"M {coords} Z" if closed else f"M {coords}"


def _fmt_elevation(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def build_svg(result: ContourResult, line_weight_mm: float = 0.4) -> str:
    w = f"{result.width_mm:.2f}"
    h = f"{result.height_mm:.2f}"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}mm" height="{h}mm" '
        f'viewBox="0 0 {w} {h}" fill="none" stroke="black" '
        f'stroke-width="{line_weight_mm:g}" stroke-linejoin="round" stroke-linecap="round">'
    ]
    for level in result.levels:
        parts.append(f'  <g data-elevation="{_fmt_elevation(level.elevation)}">')
        for line in level.lines:
            parts.append(f'    <path d="{_path_d(line)}"/>')
        parts.append("  </g>")
    parts.append("</svg>")
    return "\n".join(parts)
