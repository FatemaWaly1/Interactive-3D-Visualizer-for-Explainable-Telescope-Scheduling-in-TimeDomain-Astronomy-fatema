"""
Schedule timing: slew and end times from angular distance + telescope slew_speed.
Uses same logic as SchedulePanel.update_schedule() with hand-computed expected values.
"""
import math
import unittest
import numpy as np

from models.coordinates import ra_dec_to_xyz
from models.telescope import Telescope
from services.geometry import angdist_vec


def compute_slew_end_times(tiles, telescope, distance_func):
    """
    Pure logic from schedule panel: no Qt.
    tiles: list of dicts with keys position, dwell_time (default 60).
    Returns list of (slew_s, end_s) per tile.
    """
    result = []
    prev_pos = None
    time_accum = 0.0
    for tile in tiles:
        dwell = tile.get("dwell_time", 60.0)
        slew = 0.0
        if telescope and prev_pos is not None and distance_func:
            dist_rad = distance_func(prev_pos, tile["position"])
            dist_deg = math.degrees(dist_rad)
            slew = dist_deg / telescope.slew_speed
        time_accum += slew + dwell
        result.append((slew, time_accum))
        prev_pos = tile["position"]
    return result


class TestScheduleTiming(unittest.TestCase):
    def setUp(self):
        self.slew_speed = 5.0  # °/s
        self.telescope = Telescope("test", slew_speed=self.slew_speed, dwell_time=60.0)

    def _tiles_with_positions(self, ra_dec_list, dwell=60.0):
        tiles = []
        for ra, dec in ra_dec_list:
            pos = ra_dec_to_xyz(ra, dec)
            tiles.append({
                "ra": ra, "dec": dec, "prob": 0.01,
                "position": np.array(pos),
                "dwell_time": dwell,
            })
        return tiles

    def test_first_tile_zero_slew_end_equals_dwell(self):
        tiles = self._tiles_with_positions([(288.0, 15.0)])
        got = compute_slew_end_times(tiles, self.telescope, angdist_vec)
        self.assertEqual(len(got), 1)
        self.assertAlmostEqual(got[0][0], 0.0, places=2)
        self.assertAlmostEqual(got[0][1], 60.0, places=2)

    def test_two_tiles_hand_computed_slew_and_end(self):
        # Tile 1 (288°, 15°) -> Tile 2 (0°, 45°): cos(d)≈0.39407 -> d≈66.88° -> slew≈13.38 s
        tiles = self._tiles_with_positions([(288.0, 15.0), (0.0, 45.0)])
        got = compute_slew_end_times(tiles, self.telescope, angdist_vec)
        self.assertEqual(len(got), 2)
        self.assertAlmostEqual(got[0][0], 0.0, places=2)
        self.assertAlmostEqual(got[0][1], 60.0, places=2)
        # Slew 1->2 ≈ 13.36–13.38 s, End = 60 + slew + 60
        self.assertAlmostEqual(got[1][0], 13.36, places=1)
        self.assertAlmostEqual(got[1][1], 133.36, places=1)

    def test_three_tiles_cumulative_end_times(self):
        # (288,15) -> (0,45) -> (0,5): second slew ~8 s (40° at 5 °/s)
        tiles = self._tiles_with_positions([
            (288.0, 15.0),
            (0.0, 45.0),
            (0.0, 5.0),
        ])
        got = compute_slew_end_times(tiles, self.telescope, angdist_vec)
        self.assertEqual(len(got), 3)
        self.assertAlmostEqual(got[0][1], 60.0, places=2)
        self.assertAlmostEqual(got[1][1], 133.36, places=1)
        # End3 = End2 + slew_2->3 + 60; slew_2->3 = 40°/5 = 8 s -> 201.36
        self.assertAlmostEqual(got[2][1], 201.36, places=1)
        self.assertAlmostEqual(got[2][0], 8.0, places=2)

    def test_no_telescope_all_slew_zero(self):
        tiles = self._tiles_with_positions([(0.0, 0.0), (10.0, 10.0)])
        got = compute_slew_end_times(tiles, None, angdist_vec)
        self.assertAlmostEqual(got[0][0], 0.0, places=2)
        self.assertAlmostEqual(got[1][0], 0.0, places=2)
        self.assertAlmostEqual(got[0][1], 60.0, places=2)
        self.assertAlmostEqual(got[1][1], 120.0, places=2)


if __name__ == "__main__":
    unittest.main()
