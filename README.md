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

## Quick start (prebuilt image — recommended)

Every push to `main` is automatically built for `linux/amd64` and
`linux/arm64` and published to GitHub Container Registry. No build step
needed on your server:

```yaml
services:
  contour-studio:
    image: ghcr.io/knottedcables/contourstudio:latest
    ports:
      - "8080:8080"
    volumes:
      - contour-data:/data   # tile cache + saved designs
    restart: unless-stopped

volumes:
  contour-data:
```

Paste that into a Portainer/Dockhand stack (or save as `docker-compose.yml`
and run `docker compose up -d`), then open `http://<host>:8080`.

To keep the data on a NAS instead of a Docker-managed volume, replace the
volume line with a path, e.g. `- /mnt/nfs-docker/contour-studio/data:/data`,
and drop the trailing `volumes:` block.

To update later: `docker compose pull && docker compose up -d`.

The container needs outbound internet (elevation tiles, basemap tiles,
Overpass, Nominatim). There is no authentication — run it on a trusted
LAN or behind a VPN (e.g. Tailscale); don't expose it directly to the
internet.

## Build from source instead

```bash
git clone https://github.com/knottedcables/contourstudio.git
cd contourstudio
docker compose up -d --build
```

(The included `docker-compose.yml` uses `build: .` for exactly this.)

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
docker-compose.yml       Build-from-source stack definition
.github/workflows/       Auto-build + publish to ghcr.io on push
contour-studio-spec.md   Original project brief (milestones M1–M7)
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

## License

[MIT](LICENSE)
