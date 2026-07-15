#!/usr/bin/env python3
"""M1 CLI: bbox in -> contour SVG out.

Usage:
    python scripts/render_bbox.py --bbox " -121.86,46.80,-121.66,46.92" \
        --out output/rainier.svg --interval 200 --units ft
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.pipeline import Settings
from app.render import render_svg


def main() -> None:
    p = argparse.ArgumentParser(description="Render a contour SVG for a bbox.")
    p.add_argument("--bbox", required=True, help="west,south,east,north (WGS84 degrees)")
    p.add_argument("--out", required=True, help="output SVG path")
    p.add_argument("--interval", type=float, default=40.0, help="contour interval")
    p.add_argument("--units", choices=["ft", "m"], default="ft")
    p.add_argument("--smoothing", type=float, default=3.0, help="Gaussian sigma, DEM px")
    p.add_argument("--simplify", type=float, default=0.2, help="tolerance, mm")
    p.add_argument("--min-ring", type=float, default=0.5, help="min ring area, mm^2")
    p.add_argument("--line-weight", type=float, default=0.4, help="stroke width, mm")
    p.add_argument("--width-mm", type=float, default=228.6)
    args = p.parse_args()

    bbox = tuple(float(v) for v in args.bbox.split(","))
    if len(bbox) != 4:
        p.error("bbox must have exactly 4 comma-separated numbers")

    settings = Settings(
        interval=args.interval,
        units=args.units,
        smoothing=args.smoothing,
        simplify=args.simplify,
        min_ring=args.min_ring,
    )
    started = time.time()
    svg = render_svg(bbox, settings, width_mm=args.width_mm, line_weight_mm=args.line_weight)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg)

    n_levels = svg.count("<g ")
    n_paths = svg.count("<path")
    print(
        f"{out}  |  {n_levels} elevation levels, {n_paths} paths, "
        f"{out.stat().st_size / 1024:.0f} KB, {time.time() - started:.1f}s"
    )


if __name__ == "__main__":
    main()
