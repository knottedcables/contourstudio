# Contour Studio

Self-hosted web app that generates clean, smooth contour-line maps of any
location, designed for laser etching (tumblers, coasters). Runs as a single
Docker container.

**Status: in development.** See `contour-studio-spec.md` for the full project
brief and milestone plan (M1–M7).

## What it does

1. Pan/zoom a map in your browser, or search for a place by name.
2. Drag a selection box over the area you want.
3. Tune style sliders (contour interval, smoothing, detail…) with a live preview.
4. Export as SVG (for LightBurn/Inkscape) or high-res PNG.

Output contains contour lines and optional water outlines only — no labels,
roads, or basemap imagery.

## Running it

*(Deployment instructions will be added at milestone M7 — Dockerization.)*

## Development

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest                      # run unit tests
```

Project layout:

```
app/          FastAPI backend + contour rendering pipeline
app/static/   Single-page frontend (MapLibre GL JS, vanilla JS)
scripts/      CLI tools (M1 proof-of-concept renderer, verification scripts)
tests/        Unit tests
output/       Generated SVGs (test renders kept in output/test_renders/)
```
