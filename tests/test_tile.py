"""Tests for models.tile.Tile. TypedDict schema."""
import unittest
from models.tile import Tile


class TestTile(unittest.TestCase):
    def test_init_sets_attributes(self):
        t = Tile(
            ra=10.0,
            dec=-5.0,
            prob=0.1,
            position=(0.5, 0.2, 0.8),
            source="file",
        )
        self.assertEqual(t["ra"], 10.0)
        self.assertEqual(t["dec"], -5.0)
        self.assertEqual(t["prob"], 0.1)
        self.assertEqual(t["position"], (0.5, 0.2, 0.8))
        self.assertEqual(t["source"], "file")

    def test_default_source_is_file(self):
        t = Tile(ra=0.0, dec=0.0, prob=0.0, position=(1, 0, 0))
        self.assertIsInstance(t, dict)

if __name__ == "__main__":
    unittest.main()
