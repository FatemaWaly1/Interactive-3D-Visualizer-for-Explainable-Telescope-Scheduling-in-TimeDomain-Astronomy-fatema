"""Tests for services.schedule_io: load/save schedule files."""
import json
import os
import tempfile
import unittest

from services.schedule_io import (
    FOM_METADATA_KEY,
    load_schedule_file,
    parse_deadlines_finite,
    save_schedule_file,
)


class TestParseDeadlines(unittest.TestCase):
    def test_parse_valid(self):
        self.assertEqual(parse_deadlines_finite("60, 120 , 180"), [60.0, 120.0, 180.0])

    def test_parse_empty_raises(self):
        with self.assertRaises(ValueError):
            parse_deadlines_finite("")


class TestLoadScheduleFile(unittest.TestCase):
    def test_load_json_dict_with_tiles_key(self):
        payload = {"tiles": [{"ra": 10.0, "dec": -5.0, "prob": 0.1}]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(payload, f)
            path = f.name
        try:
            got, meta = load_schedule_file(path)
            self.assertEqual(got, payload["tiles"])
            self.assertIsNone(meta)
        finally:
            os.remove(path)

    def test_load_json_with_fom_metadata(self):
        payload = {
            "tiles": [{"ra": 1.0, "dec": 2.0, "prob": 0.5}],
            FOM_METADATA_KEY: {"deadlines_finite": [60.0, 120.0], "last_fom": 0.7},
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(payload, f)
            path = f.name
        try:
            got, meta = load_schedule_file(path)
            self.assertEqual(got, payload["tiles"])
            self.assertEqual(meta["deadlines_finite"], [60.0, 120.0])
            self.assertEqual(meta["last_fom"], 0.7)
        finally:
            os.remove(path)

    def test_load_json_list_directly(self):
        payload = [{"ra": 1.0, "dec": 2.0, "prob": 0.5}]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(payload, f)
            path = f.name
        try:
            got, meta = load_schedule_file(path)
            self.assertEqual(got, payload)
            self.assertIsNone(meta)
        finally:
            os.remove(path)

    def test_unsupported_extension_raises(self):
        with self.assertRaises(ValueError):
            load_schedule_file("schedule.txt")


class TestSaveScheduleFile(unittest.TestCase):
    def test_save_json_roundtrip(self):
        tiles = [{"ra": 10.0, "dec": -5.0, "prob": 0.1, "dwell_time": 60.0}]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            save_schedule_file(path, tiles)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("tiles", data)
            self.assertEqual(data["tiles"], tiles)
            self.assertNotIn(FOM_METADATA_KEY, data)
        finally:
            os.remove(path)

    def test_save_json_with_metadata(self):
        tiles = [{"ra": 10.0, "dec": -5.0, "prob": 0.1}]
        meta = {"deadlines_finite": [60.0], "last_fom": 0.5}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            save_schedule_file(path, tiles, fom_metadata=meta)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data[FOM_METADATA_KEY], meta)
        finally:
            os.remove(path)

    def test_unsupported_extension_raises(self):
        with self.assertRaises(ValueError):
            save_schedule_file("out.txt", [])


if __name__ == "__main__":
    unittest.main()
