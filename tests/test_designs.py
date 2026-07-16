"""Saved-design storage tests, isolated in a temp DATA_DIR."""

import json

import pytest

from app import designs

BBOX = [-120.15, 39.0, -119.9, 39.25]
SETTINGS = {"interval": 200, "units": "ft", "smoothing": 3.0, "water": True}


@pytest.fixture(autouse=True)
def tmp_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    return tmp_path


class TestDesignStorage:
    def test_save_and_get_roundtrip(self):
        saved = designs.save_design("Tahoe mug", BBOX, SETTINGS)
        loaded = designs.get_design(saved["id"])
        assert loaded["name"] == "Tahoe mug"
        assert loaded["bbox"] == BBOX
        assert loaded["settings"] == SETTINGS
        assert loaded["created"] and loaded["modified"]

    def test_list_sorted_newest_first(self):
        a = designs.save_design("first", BBOX, SETTINGS)
        b = designs.save_design("second", BBOX, SETTINGS)
        b["modified"] = "2099-01-01T00:00:00+00:00"
        designs._path(b["id"]).write_text(json.dumps(b))
        names = [d["name"] for d in designs.list_designs()]
        assert names == ["second", "first"]

    def test_update_keeps_created(self):
        saved = designs.save_design("v1", BBOX, SETTINGS)
        updated = designs.save_design("v2", BBOX, SETTINGS, design_id=saved["id"])
        assert updated["id"] == saved["id"]
        assert updated["created"] == saved["created"]
        assert len(designs.list_designs()) == 1

    def test_delete(self):
        saved = designs.save_design("gone", BBOX, SETTINGS)
        assert designs.delete_design(saved["id"]) is True
        assert designs.get_design(saved["id"]) is None
        assert designs.delete_design(saved["id"]) is False

    def test_path_traversal_rejected(self):
        with pytest.raises(ValueError):
            designs.get_design("../../etc/passwd")
        with pytest.raises(ValueError):
            designs.delete_design("abc")  # wrong shape

    def test_corrupt_file_skipped_in_list(self, tmp_data_dir):
        designs.save_design("good", BBOX, SETTINGS)
        (tmp_data_dir / "designs" / "0123456789ab.json").write_text("{not json")
        assert [d["name"] for d in designs.list_designs()] == ["good"]
