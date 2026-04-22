import unittest
from models.schedule import Schedule
from models.telescope import Telescope

class TestSchTele(unittest.TestCase):
    def setUp(self):
        self.schedule = Schedule()
        self.tile1 = {"ra": 10.0, "dec": -5.0, "prob": 0.1}
        self.tile2 = {"ra": 20.0, "dec": 5.0, "prob": 0.2}

    def test_add_tile_adds_new_tile_and_returns_true(self):
        result = self.schedule.add_tile(self.tile1)
        self.assertTrue(result)
        self.assertIn(self.tile1, self.schedule.selected_tiles)
        self.assertEqual(self.schedule.get_count(), 1)

    def test_add_tile_not_add_duplicates(self):
        self.schedule.add_tile(self.tile1)
        result = self.schedule.add_tile(self.tile1)
        self.assertFalse(result)
        self.assertEqual(self.schedule.get_count(), 1)

    def test_is_selected_reports_correctly(self):
        self.schedule.add_tile(self.tile1)
        self.assertTrue(self.schedule.is_selected(self.tile1))
        self.assertFalse(self.schedule.is_selected(self.tile2))

    def test_get_tiles_returns_copy(self):
        self.schedule.add_tile(self.tile1)
        tiles_copy = self.schedule.get_tiles()
        tiles_copy.append(self.tile2)
        self.assertEqual(self.schedule.get_count(), 1)
        self.assertNotIn(self.tile2, self.schedule.selected_tiles)

    def test_clear_empties_schedule(self):
        self.schedule.add_tile(self.tile1)
        self.schedule.add_tile(self.tile2)
        self.schedule.clear()

        self.assertEqual(self.schedule.get_count(), 0)
        self.assertEqual(self.schedule.get_tiles(), [])

    def test_init_sets_attributes(self):
        t = Telescope(name="TestScope", slew_speed=1.5, dwell_time=60.0)

        self.assertEqual(t.name, "TestScope")
        self.assertEqual(t.slew_speed, 1.5)
        self.assertEqual(t.dwell_time, 60.0)

if __name__ == '__main__':
    unittest.main()
