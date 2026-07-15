"""Elevation data: fetch, cache, decode, and stitch AWS terrarium tiles.

Tiles are 256x256 PNGs where elevation in meters is encoded in the pixel
colors: elevation = (R * 256 + G + B / 256) - 32768.

All tile math uses the standard "slippy map" Web Mercator scheme: at zoom z
the world is a square of 2^z x 2^z tiles (256 * 2^z pixels on a side).
"""

from __future__ import annotations

import math
import os
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

import numpy as np
import requests
from PIL import Image

TILE_SIZE = 256
MAX_ZOOM = 15  # highest zoom published for the terrarium dataset
TILE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
USER_AGENT = "contour-studio/0.1"


def data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "data"))


def decode_terrarium(rgb: np.ndarray) -> np.ndarray:
    """Decode a (..., 3) uint8 RGB array into elevation in meters (float32)."""
    rgb = rgb.astype(np.float32)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    return (r * 256.0 + g + b / 256.0) - 32768.0


def lonlat_to_pixel(lon: float, lat: float, zoom: int) -> tuple[float, float]:
    """Global Web Mercator pixel coordinates of a lon/lat point at a zoom.

    x grows east from the antimeridian, y grows south from the north edge.
    """
    n = TILE_SIZE * (2**zoom)
    x = (lon + 180.0) / 360.0 * n
    lat_rad = math.radians(lat)
    y = (1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * n
    return x, y


def bbox_pixel_span(bbox: tuple[float, float, float, float], zoom: int) -> tuple[float, float]:
    """(width_px, height_px) that the bbox covers at a zoom level."""
    west, south, east, north = bbox
    x0, y0 = lonlat_to_pixel(west, north, zoom)  # top-left
    x1, y1 = lonlat_to_pixel(east, south, zoom)  # bottom-right
    return x1 - x0, y1 - y0


def zoom_for_bbox(bbox: tuple[float, float, float, float], target_px: int = 1024) -> int:
    """Largest zoom (capped at MAX_ZOOM) where the bbox fits in target_px.

    Because each zoom step doubles the span, the chosen zoom yields a span
    in (target_px/2, target_px] unless capped by MAX_ZOOM.
    """
    for zoom in range(MAX_ZOOM, 0, -1):
        w, h = bbox_pixel_span(bbox, zoom)
        if max(w, h) <= target_px:
            return zoom
    return 1


def _tile_cache_path(z: int, x: int, y: int) -> Path:
    return data_dir() / "tiles" / "terrarium" / str(z) / str(x) / f"{y}.png"


def fetch_tile(z: int, x: int, y: int, session: requests.Session | None = None) -> np.ndarray:
    """Return one tile as a (256, 256) float32 elevation grid, disk-cached."""
    cache = _tile_cache_path(z, x, y)
    if cache.exists():
        png_bytes = cache.read_bytes()
    else:
        url = TILE_URL.format(z=z, x=x, y=y)
        http = session or requests
        last_err = None
        for _attempt in range(3):
            try:
                resp = http.get(url, timeout=20, headers={"User-Agent": USER_AGENT})
                resp.raise_for_status()
                png_bytes = resp.content
                break
            except requests.RequestException as err:
                last_err = err
        else:
            raise RuntimeError(f"Could not download elevation tile {z}/{x}/{y}: {last_err}")
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(png_bytes)
    img = Image.open(BytesIO(png_bytes)).convert("RGB")
    return decode_terrarium(np.asarray(img))


def dem_for_bbox(
    bbox: tuple[float, float, float, float], target_px: int = 1024
) -> tuple[np.ndarray, int]:
    """Stitch tiles covering the bbox and crop to it.

    Returns (grid, zoom): grid is a float32 elevation array in meters, row 0
    at the north edge, column 0 at the west edge. Pixel spacing is uniform in
    Web Mercator, which is locally shape-preserving, so grid aspect matches
    real-world aspect at the bbox center.
    """
    west, south, east, north = bbox
    if not (west < east and south < north):
        raise ValueError(f"Invalid bbox (need west<east and south<north): {bbox}")
    zoom = zoom_for_bbox(bbox, target_px)

    px0, py0 = lonlat_to_pixel(west, north, zoom)
    px1, py1 = lonlat_to_pixel(east, south, zoom)
    tx0, ty0 = int(px0 // TILE_SIZE), int(py0 // TILE_SIZE)
    tx1, ty1 = int(math.ceil(px1 / TILE_SIZE)) - 1, int(math.ceil(py1 / TILE_SIZE)) - 1

    session = requests.Session()
    coords = [(z, x, y) for z in [zoom] for y in range(ty0, ty1 + 1) for x in range(tx0, tx1 + 1)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        tiles = list(pool.map(lambda c: fetch_tile(*c, session=session), coords))

    cols = tx1 - tx0 + 1
    rows = ty1 - ty0 + 1
    mosaic = np.empty((rows * TILE_SIZE, cols * TILE_SIZE), dtype=np.float32)
    for i, (_z, x, y) in enumerate(coords):
        r, c = y - ty0, x - tx0
        mosaic[r * TILE_SIZE : (r + 1) * TILE_SIZE, c * TILE_SIZE : (c + 1) * TILE_SIZE] = tiles[i]

    left = int(px0 - tx0 * TILE_SIZE)
    top = int(py0 - ty0 * TILE_SIZE)
    right = int(math.ceil(px1 - tx0 * TILE_SIZE))
    bottom = int(math.ceil(py1 - ty0 * TILE_SIZE))
    return mosaic[top:bottom, left:right], zoom
