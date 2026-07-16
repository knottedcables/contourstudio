"""Water outlines from OSM via the Overpass API (spec section 5).

Overpass can be slow or down; callers must treat RuntimeError from
water_lines_cached() as a non-fatal warning and render without water.

Responses are cached in-process per bbox: the live preview re-renders on
every slider change and must not re-query Overpass each time (their usage
policy is ~1 request/s). Failures are also cached briefly so a dead
Overpass doesn't add a timeout wait to every render.
"""

from __future__ import annotations

import os
import time

import numpy as np
import requests

USER_AGENT = "contour-studio/0.1"
TIMEOUT_S = 12
FAILURE_RETRY_S = 120


def overpass_url() -> str:
    return os.environ.get("OVERPASS_URL", "https://overpass-api.de/api/interpreter")


def _query(bbox: tuple[float, float, float, float]) -> str:
    west, south, east, north = bbox
    return f"""
[out:json][timeout:{TIMEOUT_S}][bbox:{south},{west},{north},{east}];
(
  way["natural"="water"];
  way["natural"="coastline"];
  way["waterway"="riverbank"];
  relation["natural"="water"];
  relation["waterway"="riverbank"];
);
out geom;
"""


def parse_overpass(data: dict) -> list[np.ndarray]:
    """Extract shoreline polylines as (N, 2) lon/lat arrays.

    Water bodies arrive as tagged ways or as relations whose member ways
    carry the geometry; members are deduplicated against standalone ways.
    """
    lines: list[np.ndarray] = []
    seen: set[int] = set()

    def add(way_id: int, geometry: list[dict]) -> None:
        if way_id in seen or not geometry:
            return
        seen.add(way_id)
        arr = np.array([[pt["lon"], pt["lat"]] for pt in geometry], dtype=np.float64)
        if len(arr) >= 2:
            lines.append(arr)

    for el in data.get("elements", []):
        if el.get("type") == "way":
            add(el["id"], el.get("geometry", []))
        elif el.get("type") == "relation":
            for member in el.get("members", []):
                if member.get("type") == "way":
                    add(member["ref"], member.get("geometry") or [])
    return lines


def fetch_water_lines(bbox: tuple[float, float, float, float]) -> list[np.ndarray]:
    resp = requests.post(
        overpass_url(),
        data={"data": _query(bbox)},
        timeout=(5, TIMEOUT_S + 5),
        headers={"User-Agent": USER_AGENT},
    )
    resp.raise_for_status()
    return parse_overpass(resp.json())


_cache: dict[tuple, tuple[float, list[np.ndarray] | Exception]] = {}


def water_lines_cached(bbox: tuple[float, float, float, float]) -> list[np.ndarray]:
    key = tuple(round(v, 5) for v in bbox)
    hit = _cache.get(key)
    if hit is not None:
        ts, value = hit
        if not isinstance(value, Exception):
            return value
        if time.time() - ts < FAILURE_RETRY_S:
            raise RuntimeError(_friendly(value))
    try:
        lines = fetch_water_lines(bbox)
    except Exception as err:
        _cache[key] = (time.time(), err)
        raise RuntimeError(_friendly(err))
    _cache[key] = (time.time(), lines)
    return lines


def _friendly(err: Exception) -> str:
    """One readable line for the UI status bar, not a requests stack dump."""
    if isinstance(err, requests.Timeout):
        reason = "timed out"
    elif isinstance(err, requests.ConnectionError):
        reason = "unreachable"
    elif isinstance(err, requests.HTTPError):
        reason = f"returned HTTP {err.response.status_code}"
    else:
        reason = f"error: {type(err).__name__}"
    # ASCII only: this string travels in an HTTP header
    return f"Water outlines skipped - the OSM water service (Overpass) {reason}. Contours are unaffected."
