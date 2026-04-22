"""Tests for services.telescope_io: load/save telescope store."""
import json
import os
import tempfile
import unittest
from services.telescope_io import load_telescopes, save_telescope, TELESCOPE_DB_PATH


class TestLoadTelescopes(unittest.TestCase):
    def test_missing_file_returns_empty_store(self):
        path = os.path.join(tempfile.gettempdir(), "nonexistent_telescopes_12345.json")
        if os.path.exists(path):
            os.remove(path)
        got = load_telescopes(path)
        self.assertEqual(got, {"telescopes": []})

    def test_load_valid_store(self):
        store = {"telescopes": [{"name": "T1", "slew_speed": 5.0, "dwell_time": 60.0}]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(store, f)
            path = f.name
        try:
            got = load_telescopes(path)
            self.assertEqual(got["telescopes"], store["telescopes"])
        finally:
            os.remove(path)


class TestSaveTelescope(unittest.TestCase):
    def test_save_creates_new_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "telescopes.json")
            save_telescope({"name": "NewScope", "slew_speed": 2.0, "dwell_time": 30.0}, path)
            store = load_telescopes(path)
            self.assertEqual(len(store["telescopes"]), 1)
            self.assertEqual(store["telescopes"][0]["name"], "NewScope")

    def test_save_updates_existing_by_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "telescopes.json")
            save_telescope({"name": "A", "slew_speed": 1.0, "dwell_time": 60.0}, path)
            save_telescope({"name": "A", "slew_speed": 3.0, "dwell_time": 90.0}, path)
            store = load_telescopes(path)
            self.assertEqual(len(store["telescopes"]), 1)
            self.assertEqual(store["telescopes"][0]["slew_speed"], 3.0)
            self.assertEqual(store["telescopes"][0]["dwell_time"], 90.0)


if __name__ == "__main__":
    unittest.main()
