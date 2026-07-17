"""FastAPI app: serves the single-page frontend and the render API.

Run locally:  .venv/bin/uvicorn app.main:app --port 8080
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import designs
from .pipeline import Settings
from .render import PREVIEW_TARGET_PX, render_svg, svg_to_png

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Contour Studio")


@app.middleware("http")
async def revalidate_ui_assets(request, call_next):
    """no-cache on the page + static assets: browsers must revalidate
    (cheap 304 on a LAN) instead of heuristically serving stale JS/CSS
    after the container updates."""
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static"):
        response.headers["Cache-Control"] = "no-cache"
    return response


class RenderRequest(BaseModel):
    """Request body for /render (and later /export) — spec section 7."""

    bbox: tuple[float, float, float, float]  # west, south, east, north
    interval: float = Field(default=40.0, gt=0)
    units: Literal["ft", "m"] = "ft"
    smoothing: float = Field(default=3.0, ge=0)
    simplify: float = Field(default=0.2, ge=0)
    min_ring: float = Field(default=0.5, ge=0)
    line_weight: float = Field(default=0.4, gt=0)
    water: bool = True  # wired up in M5
    width_mm: float = Field(default=228.6, gt=0)
    height_mm: float | None = Field(default=None, gt=0)
    format: Literal["svg", "png"] = "svg"  # PNG arrives in M4
    dpi: int = 600

    def to_settings(self) -> Settings:
        return Settings(
            interval=self.interval,
            units=self.units,
            smoothing=self.smoothing,
            simplify=self.simplify,
            min_ring=self.min_ring,
        )


def _render(req: RenderRequest, target_px: int) -> tuple[str, dict]:
    """Returns (svg, headers) — a water failure becomes an X-Warning header
    the UI surfaces without blocking the render (fail soft)."""
    try:
        svg, warning = render_svg(
            req.bbox,
            req.to_settings(),
            width_mm=req.width_mm,
            height_mm=req.height_mm,
            line_weight_mm=req.line_weight,
            target_px=target_px,
            water=req.water,
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except RuntimeError as err:  # elevation tile download failed
        raise HTTPException(status_code=502, detail=str(err))
    headers = {}
    if warning:
        headers["X-Warning"] = warning.encode("ascii", "replace").decode()
    return svg, headers


@app.post("/render")
def render(req: RenderRequest) -> Response:
    """Preview render: reduced resolution for speed; export runs full quality."""
    svg, headers = _render(req, target_px=PREVIEW_TARGET_PX)
    return Response(content=svg, media_type="image/svg+xml", headers=headers)


@app.post("/export")
def export(req: RenderRequest) -> Response:
    """Full-quality export as downloadable SVG or PNG (at req.dpi)."""
    svg, headers = _render(req, target_px=1024)
    if req.format == "svg":
        return Response(
            content=svg,
            media_type="image/svg+xml",
            headers={"Content-Disposition": 'attachment; filename="contour.svg"', **headers},
        )
    try:
        png = svg_to_png(svg, dpi=req.dpi)
    except OSError as err:  # native cairo library missing/broken
        raise HTTPException(status_code=500, detail=f"PNG rendering unavailable: {err}")
    return Response(
        content=png,
        media_type="image/png",
        headers={"Content-Disposition": 'attachment; filename="contour.png"', **headers},
    )


class DesignIn(BaseModel):
    """Body for POST /designs; include id to update an existing design."""

    name: str = Field(min_length=1, max_length=120)
    bbox: tuple[float, float, float, float]
    settings: dict
    id: str | None = None


@app.get("/designs")
def designs_list() -> list[dict]:
    return designs.list_designs()


@app.post("/designs", status_code=201)
def designs_save(body: DesignIn) -> dict:
    try:
        return designs.save_design(body.name, list(body.bbox), body.settings, body.id)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@app.get("/designs/{design_id}")
def designs_get(design_id: str) -> dict:
    try:
        design = designs.get_design(design_id)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    if design is None:
        raise HTTPException(status_code=404, detail="Design not found")
    return design


@app.delete("/designs/{design_id}", status_code=204)
def designs_delete(design_id: str) -> None:
    try:
        if not designs.delete_design(design_id):
            raise HTTPException(status_code=404, detail="Design not found")
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
