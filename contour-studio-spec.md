# Contour Studio — Project Specification

Self-hosted web app that generates clean, smooth contour-line maps of any location for laser etching (tumblers, coasters). Replaces contourmap.app (area limits, per-map cost) and contourmapcreator.urgr8.ch (jagged contours). Runs as a single Docker container deployed via Portainer.

**This document is written to be handed to Claude Code as the project brief.** Work through the milestones in order; each has acceptance criteria.

---

## 1. User workflow

1. Open the app in a browser. Pan/zoom an interactive map; search for a place by name.
2. Drag/resize a selection box over the area of interest.
3. Adjust style sliders and watch a live preview of the contour rendering.
4. Export as SVG (primary) or high-res PNG.
5. Optionally save the design (location + settings) to reload and re-export later.

No labels, no roads, no basemap imagery in the output — contour lines and optional water outlines only.

## 2. Tech stack

| Layer | Choice | Rationale |
|---|---|---|
| Backend | Python 3.12 + FastAPI | Best ecosystem for DEM/geometry work (numpy, scipy, shapely, contourpy) |
| Contouring | `contourpy` + `scipy` + `shapely` | Fine control over smoothing — the whole point of the project |
| Frontend | Single-page app: MapLibre GL JS + vanilla JS (or lightweight Vue via CDN) | Interactive map, no build-step complexity required |
| Basemap (UI only) | OpenStreetMap raster tiles (or OpenFreeMap vector) | Free, no key; only for on-screen selection, never in exports |
| Elevation data | AWS Terrain Tiles ("terrarium"), s3://elevation-tiles-prod | Free, no API key, global coverage, automatically best-available resolution (~10 m US / ~30 m global). Fits "mostly US, occasional international" |
| Water outlines | OSM via Overpass API | Free; fetch water polygons for the selected bbox |
| Storage | JSON files in a mounted volume | Saved designs with zero database overhead |
| Container | Single Docker image, one exposed port (8080) | Easy Portainer stack |

## 3. Elevation data details

- Tile URL: `https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png`
- Decode: `elevation_m = (R * 256 + G + B / 256) - 32768`
- Choose zoom so the selection spans roughly 512–1024 px of DEM; stitch tiles into one numpy grid, crop to the bbox.
- Cache downloaded tiles on disk (mounted volume) so repeat renders are fast and offline-friendly.
- Handle nodata/ocean gracefully (values at/below sea level).

## 4. Contour quality pipeline (the core differentiator)

The existing free tool's contours are jagged. Fix with this pipeline, each stage user-tunable:

1. **DEM upsampling** — bicubic upsample of the elevation grid 2–4× before contouring, so contours aren't quantized to pixel edges.
2. **DEM smoothing** — Gaussian filter (`scipy.ndimage.gaussian_filter`), sigma exposed as the "Smoothing" slider. This is what removes stair-step artifacts at the source.
3. **Contour extraction** — `contourpy` at the user's interval (ft or m; interval slider, e.g. 5–500 ft).
4. **Polyline smoothing** — Chaikin corner-cutting (2–3 iterations) or shapely `simplify` + spline fit on each contour ring for silky curves.
5. **Simplification** — Douglas-Peucker tolerance slider to control node count (smaller SVG, cleaner laser paths).
6. **Small-ring culling** — drop closed rings below a minimum area/length threshold ("Detail" slider) to remove speckle on rough terrain.

Preserve ring closure (closed loops stay closed) and clip all geometry to the selection bbox.

## 5. Water outlines

- Toggleable per design (default on): query Overpass for `natural=water`, `natural=coastline`, `waterway=riverbank` polygons in the bbox.
- Render shorelines as polylines at contour line weight, same smoothing pipeline.
- Overpass can be slow/down: fail soft — render contours without water and surface a non-blocking warning in the UI.

## 6. Frontend controls

- Place search (Nominatim, free, no key) + pan/zoom map.
- Draggable/resizable selection rectangle; optional aspect-ratio lock field (free entry, e.g. 9:4) — nice-to-have, not required for v1.
- Sliders/inputs: contour interval (with ft/m toggle), smoothing, simplification, detail (min ring size), line weight.
- Toggle: water outlines.
- Live preview: debounce slider changes, POST settings to `/render`, display returned SVG inline. Preview may render at reduced resolution for speed; export runs full quality.
- Export buttons: SVG, PNG (with DPI selector: 300/600).
- Save/Load design panel (name, list, load, delete).

## 7. Render API

`POST /render` and `POST /export` accept:

```json
{
  "bbox": [west, south, east, north],
  "interval": 40, "units": "ft",
  "smoothing": 3.0, "simplify": 1.0, "min_ring": 0.5,
  "line_weight": 0.4, "water": true,
  "width_mm": 228.6, "height_mm": 101.6,
  "format": "svg", "dpi": 600
}
```

- SVG export: physical dimensions in `mm` on the root element, `viewBox` matched, strokes in mm, `fill="none"`, `stroke="black"`, one `<path>` per contour ring grouped by elevation level (`<g data-elevation="...">`) so levels can be selected individually in Inkscape/LightBurn.
- PNG export: rasterize the same SVG at the chosen DPI (cairosvg).

## 8. Saved designs

- JSON file per design in `/data/designs/` (mounted volume): name, bbox, all settings, created/modified timestamps.
- Endpoints: `GET /designs`, `POST /designs`, `GET /designs/{id}`, `DELETE /designs/{id}`.
- No auth (home LAN app). Keep it simple.

## 9. Docker / Portainer

Single image, multi-stage build if needed, `linux/amd64` (add arm64 to the build matrix only if requested). Portainer stack:

```yaml
services:
  contour-studio:
    build: .
    # or: image: contour-studio:latest (built locally / via Portainer build)
    ports:
      - "8080:8080"
    volumes:
      - contour-data:/data       # tile cache + saved designs
    restart: unless-stopped
volumes:
  contour-data:
```

Container needs outbound internet (elevation tiles, OSM basemap, Overpass, Nominatim).

## 10. Milestones

**M1 — Contour engine (CLI proof).** Script: bbox in → SVG out, full pipeline of §4 with hardcoded settings. *Accept:* SVG of a known mountainous bbox opens in Inkscape with visibly smooth nested contours; a lake-adjacent bbox doesn't crash.

**M2 — API + minimal UI.** FastAPI serving the SPA; map with selection box; `/render` returns SVG shown inline. *Accept:* select an area in the browser, see contours.

**M3 — Style controls + live preview.** All sliders of §6 wired with debounced re-render. *Accept:* moving Smoothing visibly changes contour character within ~2 s.

**M4 — Exports.** SVG with physical mm sizing + grouped elevation levels; PNG at selectable DPI. *Accept:* SVG imports into LightBurn/Inkscape at correct physical size; strokes are hairline-editable paths, not images.

**M5 — Water outlines.** Overpass integration with soft-fail. *Accept:* a coastal selection shows shoreline; Overpass timeout still returns contours with a warning.

**M6 — Saved designs.** JSON persistence + UI panel. *Accept:* save, restart container, reload design, re-export identical file.

**M7 — Dockerization.** Dockerfile + compose stack, tile cache volume, README with Portainer deploy steps. *Accept:* fresh deploy from the stack file works end-to-end.

If any milestone stalls, M6 (saving) and the aspect-ratio lock are the designated cut-first features.

## 11. Verification habits for the implementer

- After each render-pipeline change, regenerate a fixed set of 3 test bboxes (mountain, coastal, gentle plains) and eyeball the SVGs.
- Unit-test the terrarium decode formula and bbox→tile math (off-by-one tile errors are the classic bug).
- Validate exported SVG dimensions with a script (parse width/height/viewBox).

---

## Starter prompt for Claude Code

> Read contour-studio-spec.md in this repo and implement it milestone by milestone, starting with M1. After each milestone, stop, show me the acceptance-criteria evidence (generated files or screenshots), and wait for my go-ahead before continuing.
