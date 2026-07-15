#!/usr/bin/env python3
"""Regenerate the three fixed verification bboxes (CLAUDE.md / spec section 11).

Run after ANY render-pipeline change, then eyeball the SVGs in
output/test_renders/.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.pipeline import Settings
from app.render import render_svg

OUT_DIR = Path(__file__).resolve().parent.parent / "output" / "test_renders"

# name -> (bbox, interval in ft) — intervals chosen so each terrain type
# yields a useful number of lines (Rainier has ~12,000 ft of relief, the
# Kansas plains only ~100 ft)
CASES = {
    "rainier": ((-121.86, 46.80, -121.66, 46.92), 200.0),
    "bigsur": ((-121.98, 36.42, -121.86, 36.52), 100.0),
    "kansas": ((-98.60, 38.30, -98.40, 38.42), 10.0),
}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, (bbox, interval) in CASES.items():
        started = time.time()
        svg = render_svg(bbox, Settings(interval=interval, units="ft"))
        out = OUT_DIR / f"{name}.svg"
        out.write_text(svg)
        print(
            f"{name:8s}  {svg.count('<g '):3d} levels  {svg.count('<path'):5d} paths  "
            f"{out.stat().st_size / 1024:5.0f} KB  {time.time() - started:5.1f}s"
        )


if __name__ == "__main__":
    main()
