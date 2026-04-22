"""Tests for services.schedule_metrics: merits ladder, analyse_schedule (FoM + timing)."""

import math
import unittest

import numpy as np

from models.telescope import Telescope
from services.schedule_metrics import (
    ScheduleMetric,
    analyse_schedule,
    compute_merits_for_deadlines,
)


class TestComputeMeritsForDeadlines(unittest.TestCase):
    def test_single_inf_band_returns_unit_merit(self):
        self.assertEqual(compute_merits_for_deadlines([float("inf")]), [1.0])

    def test_two_bands_linear_ladder(self):
        m = compute_merits_for_deadlines([100.0, float("inf")])
        self.assertEqual(m, [1.0, 0.0])

    def test_three_bands_linear_ladder(self):
        m = compute_merits_for_deadlines([100.0, 200.0, float("inf")])
        self.assertEqual(m, [1.0, 0.5, 0.0])


class TestAnalyseSchedule(unittest.TestCase):
    def test_zero_total_probability_returns_zero_fom(self):
        tiles = [
            {"position": np.array([1.0, 0.0, 0.0]), "prob": 0.0, "dwell_time": 10.0},
        ]
        m = analyse_schedule(
            tiles,
            telescope=None,
            start_position=None,
            deadlines_finite=[50.0],
        )
        self.assertIsInstance(m, ScheduleMetric)
        self.assertEqual(m.fom, 0.0)
        self.assertEqual(m.total_slew_s, 0.0)
        self.assertEqual(m.tile_end_times, [10.0])

    def test_single_tile_positive_prob_fom_is_finite(self):
        tiles = [
            {"position": np.array([1.0, 0.0, 0.0]), "prob": 1.0, "dwell_time": 10.0},
        ]
        m = analyse_schedule(
            tiles,
            telescope=None,
            start_position=None,
            deadlines_finite=[100.0, 200.0],
        )
        self.assertEqual(len(m.tile_end_times), 1)
        self.assertAlmostEqual(m.tile_end_times[0], 10.0, places=6)
        self.assertFalse(math.isnan(m.fom))
        self.assertGreaterEqual(m.fom, 0.0)

    def test_two_tiles_slew_when_telescope_and_start_given(self):
        t = Telescope("t", slew_speed=5.0, dwell_time=60.0)
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([0.0, 1.0, 0.0])
        tiles = [
            {"position": a, "prob": 0.5, "dwell_time": 60.0},
            {"position": b, "prob": 0.5, "dwell_time": 60.0},
        ]
        m = analyse_schedule(
            tiles,
            telescope=t,
            start_position=a,
            deadlines_finite=[500.0, 1000.0],
        )
        self.assertEqual(len(m.tile_end_times), 2)
        self.assertGreater(m.total_slew_s, 0.0)
        self.assertGreater(m.total_time_s, m.total_slew_s)


if __name__ == "__main__":
    unittest.main()
