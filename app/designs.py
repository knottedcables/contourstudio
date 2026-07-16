"""Saved designs: one JSON file per design under DATA_DIR/designs/.

A design is a location (bbox) plus every style setting needed to reproduce
an export exactly. No database, no auth — home-LAN app (spec section 8).
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .dem import data_dir

_ID_RE = re.compile(r"^[0-9a-f]{12}$")


def designs_dir() -> Path:
    d = data_dir() / "designs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(design_id: str) -> Path:
    # ids are generated hex only; reject anything else (path traversal)
    if not _ID_RE.match(design_id):
        raise ValueError(f"Invalid design id: {design_id!r}")
    return designs_dir() / f"{design_id}.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save_design(
    name: str,
    bbox: list[float],
    settings: dict,
    design_id: str | None = None,
) -> dict:
    """Create a design, or update it when design_id is given."""
    if design_id:
        existing = get_design(design_id)  # raises ValueError on bad id
        created = existing["created"] if existing else _now()
    else:
        design_id = uuid.uuid4().hex[:12]
        created = _now()
    design = {
        "id": design_id,
        "name": name,
        "bbox": list(bbox),
        "settings": settings,
        "created": created,
        "modified": _now(),
    }
    _path(design_id).write_text(json.dumps(design, indent=2))
    return design


def get_design(design_id: str) -> dict | None:
    path = _path(design_id)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def list_designs() -> list[dict]:
    designs = []
    for path in designs_dir().glob("*.json"):
        try:
            designs.append(json.loads(path.read_text()))
        except (json.JSONDecodeError, OSError):
            continue  # one corrupt file must not break the list
    designs.sort(key=lambda d: d.get("modified", ""), reverse=True)
    return designs


def delete_design(design_id: str) -> bool:
    path = _path(design_id)
    if not path.exists():
        return False
    path.unlink()
    return True
