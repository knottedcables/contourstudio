"""Validate SVG output: physical dimensions, viewBox, structure (spec sec. 11)."""

import xml.etree.ElementTree as ET

import numpy as np

from app.pipeline import ContourLevel, ContourResult
from app.svg_out import build_svg

SVG_NS = "{http://www.w3.org/2000/svg}"


def sample_result() -> ContourResult:
    ring = np.array([[10, 10], [50, 10], [50, 40], [10, 40], [10, 10]], dtype=float)
    open_line = np.array([[0, 5], [30, 25], [60, 5]], dtype=float)
    return ContourResult(
        levels=[
            ContourLevel(elevation=100, lines=[ring]),
            ContourLevel(elevation=200, lines=[ring * 0.5, open_line]),
        ],
        width_mm=228.6,
        height_mm=101.6,
    )


class TestSvgOutput:
    def setup_method(self):
        self.svg = build_svg(sample_result(), line_weight_mm=0.4)
        self.root = ET.fromstring(self.svg)

    def test_physical_mm_dimensions_match_viewbox(self):
        assert self.root.get("width") == "228.60mm"
        assert self.root.get("height") == "101.60mm"
        vb = [float(v) for v in self.root.get("viewBox").split()]
        assert vb == [0.0, 0.0, 228.6, 101.6]

    def test_stroke_styling(self):
        assert self.root.get("fill") == "none"
        assert self.root.get("stroke") == "black"
        assert self.root.get("stroke-width") == "0.4"

    def test_groups_carry_elevation(self):
        groups = self.root.findall(f"{SVG_NS}g")
        assert [g.get("data-elevation") for g in groups] == ["100", "200"]

    def test_one_path_per_line(self):
        groups = self.root.findall(f"{SVG_NS}g")
        assert len(groups[0].findall(f"{SVG_NS}path")) == 1
        assert len(groups[1].findall(f"{SVG_NS}path")) == 2

    def test_closed_ring_uses_z_open_line_does_not(self):
        groups = self.root.findall(f"{SVG_NS}g")
        ring_d = groups[0].find(f"{SVG_NS}path").get("d")
        assert ring_d.endswith("Z")
        open_d = groups[1].findall(f"{SVG_NS}path")[1].get("d")
        assert not open_d.endswith("Z")
