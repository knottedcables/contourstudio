# CLAUDE.md — Contour Studio conventions

The project brief is `contour-studio-spec.md`. Follow its milestones (M1–M7)
in order; stop after each one and show acceptance evidence before continuing.
The user is an IT manager, not a developer — explain in plain terms.

## Process rules (from the project owner)

- Commit at each milestone with a clear message (rollback points).
- After ANY change to the render pipeline, regenerate the three test bboxes
  below and eyeball the SVGs; keep unit tests passing (`pytest`).
- Third-party services (Overpass, Nominatim, tiles) must fail soft, never block.
- No features beyond the spec without asking. If stalling, cut M6 (saving)
  and the aspect-ratio lock first.

## Fixed test bboxes (§11 verification)

Regenerate all three into `output/test_renders/` after pipeline changes:

| Name | Terrain | bbox [west, south, east, north] |
|---|---|---|
| `rainier` | mountain | `[-121.86, 46.80, -121.66, 46.92]` (Mt. Rainier, WA) |
| `bigsur` | coastal | `[-121.98, 36.42, -121.86, 36.52]` (Big Sur coast, CA) |
| `kansas` | gentle plains | `[-98.60, 38.30, -98.40, 38.42]` (central Kansas) |

## Tech decisions

- Python 3.13 (Homebrew) locally via `.venv/`; Chainguard Wolfi base
  (`cgr.dev/chainguard/wolfi-base`, python 3.12) in Docker — near-zero-CVE,
  no perl. No system-Python usage (macOS ships 3.9).
- Backend: FastAPI + uvicorn. Geometry: numpy, scipy, shapely, contourpy.
  PNG export: cairosvg (needs `brew install cairo` locally; apt in Docker).
- Frontend: vanilla JS + MapLibre GL JS from CDN, no build step, all files
  in `app/static/`.
- Tile/design storage root is the `DATA_DIR` env var (default `./data`
  locally, `/data` in the container).

## Units & parameter semantics (spec leaves these open — decided here)

- `bbox` is always WGS84 lon/lat `[west, south, east, north]`.
- DEM work happens in Web Mercator pixel space; longitude is scaled by
  `cos(latitude)` so shapes are not squashed at mid latitudes.
- `smoothing` = Gaussian sigma in (upsampled) DEM pixels.
- `simplify` = Douglas-Peucker tolerance in **output mm**.
- `min_ring` = minimum closed-ring area in **output mm²** (open lines kept).
- `line_weight` = stroke width in **mm**.
- `interval` + `units` ("ft"/"m") = contour spacing; DEM is meters natively,
  convert when units is "ft".
- Ocean/nodata: clamp elevations ≤ 0 to 0 before contouring (terrarium tiles
  contain bathymetry; we never want underwater contours).

## Pipeline order (§4 — do not reorder)

decode DEM → clamp ocean → bicubic upsample (2–4×) → Gaussian smooth →
contourpy extract → Chaikin smooth (2–3 iter) → Douglas-Peucker simplify →
cull small rings → clip to bbox. Closed rings must stay closed.

## SVG output contract (§7)

Root element: physical `width`/`height` in `mm`, matching `viewBox`,
`fill="none"`, `stroke="black"`, stroke-width in mm. One `<path>` per ring,
grouped per elevation level in `<g data-elevation="...">`.

## Verification commands

```bash
source .venv/bin/activate
pytest                                  # unit tests (terrarium decode, tile math, SVG dims)
python scripts/render_test_bboxes.py    # regenerate the three fixed test SVGs
```
