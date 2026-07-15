"""Unit tests for terrarium decode and bbox->tile math (spec section 11:
'off-by-one tile errors are the classic bug')."""

import numpy as np
import pytest

from app.dem import (
    MAX_ZOOM,
    TILE_SIZE,
    bbox_pixel_span,
    decode_terrarium,
    lonlat_to_pixel,
    zoom_for_bbox,
)


class TestDecodeTerrarium:
    def test_known_values(self):
        # elevation = (R*256 + G + B/256) - 32768
        rgb = np.array(
            [
                [0, 0, 0],  # -32768 (minimum)
                [128, 0, 0],  # sea level: 128*256 = 32768 -> 0
                [128, 100, 0],  # 100 m
                [128, 0, 128],  # 0.5 m
                [134, 57, 0],  # 134*256+57-32768 = 1593 m
            ],
            dtype=np.uint8,
        )
        expected = [-32768.0, 0.0, 100.0, 0.5, 1593.0]
        np.testing.assert_allclose(decode_terrarium(rgb), expected)

    def test_output_dtype_and_shape(self):
        rgb = np.zeros((4, 4, 3), dtype=np.uint8)
        out = decode_terrarium(rgb)
        assert out.shape == (4, 4)
        assert out.dtype == np.float32


class TestTileMath:
    def test_origin_is_northwest(self):
        # lon=-180, lat=~85 (top of Web Mercator) is pixel (0, ~0)
        x, y = lonlat_to_pixel(-180.0, 85.0511287798066, 3)
        assert x == pytest.approx(0.0)
        assert y == pytest.approx(0.0, abs=1e-6)

    def test_null_island_is_center(self):
        # lon=0, lat=0 is the exact center of the world square
        for zoom in (1, 5, 10):
            n = TILE_SIZE * 2**zoom
            x, y = lonlat_to_pixel(0.0, 0.0, zoom)
            assert x == pytest.approx(n / 2)
            assert y == pytest.approx(n / 2)

    def test_pixel_coords_double_per_zoom(self):
        x5, y5 = lonlat_to_pixel(-121.7, 46.9, 5)
        x6, y6 = lonlat_to_pixel(-121.7, 46.9, 6)
        assert x6 == pytest.approx(2 * x5)
        assert y6 == pytest.approx(2 * y5)

    def test_span_orientation_positive(self):
        # north row must come out ABOVE south row (y grows southward);
        # getting this backwards flips the map vertically
        w, h = bbox_pixel_span((-121.86, 46.80, -121.66, 46.92), 12)
        assert w > 0 and h > 0


class TestZoomSelection:
    def test_span_within_target(self):
        bbox = (-121.86, 46.80, -121.66, 46.92)
        zoom = zoom_for_bbox(bbox, target_px=1024)
        w, h = bbox_pixel_span(bbox, zoom)
        assert max(w, h) <= 1024
        # one zoom higher would overflow (i.e. we picked the largest zoom)
        w2, h2 = bbox_pixel_span(bbox, zoom + 1)
        assert max(w2, h2) > 1024

    def test_tiny_bbox_capped_at_max_zoom(self):
        tiny = (-121.700, 46.850, -121.699, 46.851)
        assert zoom_for_bbox(tiny) == MAX_ZOOM
