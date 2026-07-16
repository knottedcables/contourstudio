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

from .pipeline import Settings
from .render import render_svg

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Contour Studio")


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


@app.post("/render")
def render(req: RenderRequest) -> Response:
    """Preview render: reduced resolution for speed; export runs full quality."""
    try:
        svg = render_svg(
            req.bbox,
            req.to_settings(),
            width_mm=req.width_mm,
            line_weight_mm=req.line_weight,
            target_px=512,  # preview quality
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except RuntimeError as err:  # elevation tile download failed
        raise HTTPException(status_code=502, detail=str(err))
    return Response(content=svg, media_type="image/svg+xml")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
