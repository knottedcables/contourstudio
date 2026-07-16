"""Water outline tests — Overpass JSON parsing and pipeline clipping,
no network involved."""

import numpy as np

from app.pipeline import Settings, extract_contours
from app.water import parse_overpass


def _geom(coords):
    return [{"lon": lon, "lat": lat} for lon, lat in coords]


class TestParseOverpass:
    def test_ways_and_relation_members(self):
        data = {
            "elements": [
                {"type": "way", "id": 1, "geometry": _geom([(0, 0), (1, 0), (1, 1)])},
                {
                    "type": "relation",
                    "id": 99,
                    "members": [
                        {"type": "way", "ref": 2, "geometry": _geom([(2, 2), (3, 3)])},
                        {"type": "node", "ref": 5},  # ignored
                    ],
                },
            ]
        }
        lines = parse_overpass(data)
        assert len(lines) == 2
        assert lines[0].shape == (3, 2)

    def test_member_way_deduplicated_against_standalone(self):
        geometry = _geom([(0, 0), (1, 1)])
        data = {
            "elements": [
                {"type": "way", "id": 7, "geometry": geometry},
                {
                    "type": "relation",
                    "id": 99,
                    "members": [{"type": "way", "ref": 7, "geometry": geometry}],
                },
            ]
        }
        assert len(parse_overpass(data)) == 1

    def test_degenerate_input(self):
        data = {
            "elements": [
                {"type": "way", "id": 1},  # no geometry key
                {"type": "way", "id": 2, "geometry": _geom([(0, 0)])},  # 1 point
            ]
        }
        assert parse_overpass(data) == []


class TestWaterPipeline:
    def flat_grid(self):
        return np.full((50, 50), 100.0, dtype=np.float32)

    def test_water_clipped_to_output_rect(self):
        # a shoreline running past the east edge of the 50x50 grid
        line = np.array([[10.0, 25.0], [80.0, 25.0]])  # x extends off-grid
        result = extract_contours(
            self.flat_grid(), Settings(units="m"), width_mm=100.0, water_px=[line]
        )
        assert len(result.water) == 1
        assert result.water[0][:, 0].max() <= 100.0 + 1e-6

    def test_closed_lake_ring_stays_closed(self):
        ring = np.array(
            [[10.0, 10.0], [40.0, 10.0], [40.0, 40.0], [10.0, 40.0], [10.0, 10.0]]
        )
        result = extract_contours(
            self.flat_grid(), Settings(units="m"), width_mm=100.0, water_px=[ring]
        )
        assert len(result.water) == 1
        out = result.water[0]
        assert np.allclose(out[0], out[-1])

    def test_no_water_requested(self):
        result = extract_contours(self.flat_grid(), Settings(units="m"), width_mm=100.0)
        assert result.water == []
