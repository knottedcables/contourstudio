# Contour Studio

Self-hosted web app that generates clean, smooth contour-line maps of any
location, designed for laser etching (tumblers, coasters). Runs as a single
Docker container on port 8080.

## What it does

1. Pan/zoom a map in your browser (CyclOSM, Standard OSM, or OpenTopoMap
   basemaps), or search for a place by name.
2. Drag/resize a selection box over the area you want.
3. Tune style sliders — contour interval (ft/m), smoothing, simplification,
   detail, line weight, water outlines — with a live preview.
4. Export as SVG at exact physical size in mm (imports into
   LightBurn/Inkscape/Illustrator as editable paths, grouped by elevation)
   or PNG at 300/600 DPI.
5. Save designs (location + all settings) and reload them later.

Output contains contour lines and optional water shorelines only — no
labels, roads, or basemap imagery.

Data sources (all free, no API keys): AWS Terrain Tiles (elevation),
OpenStreetMap/Overpass (water outlines), Nominatim (place search).
Elevation tiles are cached on disk, so repeat renders of the same area are
fast and don't re-download.

## Deploy with Portainer (recommended)

1. In Portainer: **Stacks → Add stack**.
2. Name it (e.g. `contour-studio`) and either:
   - **Repository**: point at this git repository; compose path
     `docker-compose.yml`, or
   - **Web editor**: paste the contents of `docker-compose.yml`, replacing
     `build: .` with a prebuilt image reference if you build elsewhere.
3. **Deploy the stack.** First build takes a few minutes (Python
   dependencies).
4. Open `http://<host>:8080`.

The `contour-data` volume holds the elevation-tile cache and your saved
designs — they survive container rebuilds and restarts. The container needs
outbound internet access (elevation tiles, basemap tiles, Overpass,
Nominatim).

The image targets `linux/amd64`; when Portainer builds the stack on the
host, it builds for that host's architecture automatically. For a manual
cross-build: `docker build --platform linux/amd64 -t contour-studio .`

## Deploy with plain Docker Compose

```bash
docker compose up -d --build
# app at http://localhost:8080
```

## Local development (no Docker)

```bash
python3 -m venv .venv           # Python 3.12+
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8080
```

PNG export needs the native cairo library (`brew install cairo` on macOS,
`apt install libcairo2` on Debian/Ubuntu); everything else works without it.

### Tests and verification

```bash
pytest                                  # unit tests (no network needed)
python scripts/render_test_bboxes.py    # regenerate the 3 fixed test SVGs
python scripts/render_bbox.py --bbox=-121.86,46.80,-121.66,46.92 \
    --out output/rainier.svg --interval 200   # one-off CLI render
```

## Project layout

```
app/            FastAPI backend + contour render pipeline
app/static/     Single-page frontend (MapLibre GL JS, vanilla JS, no build step)
scripts/        CLI renderer + verification scripts
tests/          Unit tests
Dockerfile      Single-image build (python:3.12-slim + libcairo2)
docker-compose.yml  Portainer-ready stack definition
contour-studio-spec.md  Original project brief (milestones M1–M7)
```

## API

| Endpoint | Purpose |
|---|---|
| `POST /render` | Preview-quality SVG for the request body's bbox+settings |
| `POST /export` | Full-quality SVG or PNG (`format`, `dpi`), attachment download |
| `GET/POST /designs`, `GET/DELETE /designs/{id}` | Saved designs |

Water outline failures (Overpass down/slow) never fail a render: the
response carries an `X-Warning` header and the UI shows a non-blocking
notice.
