"""Pipeline tests on synthetic terrain — no network needed."""

import numpy as np

from app.pipeline import Settings, chaikin, extract_contours, pick_levels


def cone_grid(size: int = 60, peak_m: float = 500.0) -> np.ndarray:
    """Synthetic circular mountain: elevation falls linearly from the center."""
    y, x = np.mgrid[0:size, 0:size]
    center = (size - 1) / 2
    dist = np.hypot(x - center, y - center)
    return np.maximum(peak_m * (1 - dist / center), 0.0).astype(np.float32)


class TestChaikin:
    def test_closed_ring_stays_closed(self):
        square = np.array([[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]], dtype=float)
        out = chaikin(square, iterations=2, closed=True)
        assert np.allclose(out[0], out[-1])
        assert len(out) > len(square)  # corners were cut into more points

    def test_open_line_keeps_endpoints(self):
        line = np.array([[0, 0], [5, 10], [10, 0]], dtype=float)
        out = chaikin(line, iterations=2, closed=False)
        assert np.allclose(out[0], [0, 0])
        assert np.allclose(out[-1], [10, 0])


class TestPickLevels:
    def test_multiples_of_interval_within_range(self):
        s = Settings(interval=100, units="m")
        assert pick_levels(120.0, 450.0, s) == [200, 300, 400]

    def test_sea_level_and_below_excluded(self):
        s = Settings(interval=50, units="m")
        assert pick_levels(-30.0, 120.0, s) == [50, 100]

    def test_feet_conversion(self):
        s = Settings(interval=1000, units="ft")
        # 0..500 m is ~0..1640 ft -> levels at 1000 ft only
        assert pick_levels(0.0, 500.0, s) == [1000]


class TestExtractContours:
    def test_cone_yields_closed_nested_rings(self):
        s = Settings(interval=100, units="m", smoothing=1.0, simplify=0.1, min_ring=0.5)
        result = extract_contours(cone_grid(), s, width_mm=100.0)
        assert [lv.elevation for lv in result.levels] == [100, 200, 300, 400]
        for level in result.levels:
            assert level.lines, f"level {level.elevation} lost all its rings"
            for ring in level.lines:
                assert np.allclose(ring[0], ring[-1]), "ring not closed"

    def test_flat_grid_yields_no_levels(self):
        flat = np.full((50, 50), 7.0, dtype=np.float32)
        result = extract_contours(flat, Settings(interval=10, units="m"), width_mm=100.0)
        assert result.levels == []

    def test_ocean_clamped(self):
        # a grid that dips to -50 m must not produce negative contours
        g = cone_grid() - 50.0
        result = extract_contours(g, Settings(interval=100, units="m"), width_mm=100.0)
        assert all(lv.elevation > 0 for lv in result.levels)

    def test_output_dimensions_match_width(self):
        result = extract_contours(cone_grid(), Settings(units="m"), width_mm=228.6)
        assert result.width_mm == 228.6
        assert result.height_mm > 0
        # square grid -> square output
        assert abs(result.height_mm - 228.6) < 1e-6
