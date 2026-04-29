"""Tests for services.fom_evaluator: delegation to analyse_schedule and edge cases."""

import math
import unittest

import numpy as np

from models.coordinates import ra_dec_to_xyz
from models.telescope import Telescope
from services.fom_evaluator import evaluate_schedule_fom
from services.schedule_metrics import analyse_schedule


class TestEvaluateScheduleFom(unittest.TestCase):
    def test_fom_matches_analyse_schedule_with_positions(self) -> None:
        t = Telescope("t", slew_speed=5.0, dwell_time=60.0)
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([0.0, 1.0, 0.0])
        tiles = [
            {"position": a, "prob": 0.5, "dwell_time": 60.0},
            {"position": b, "prob": 0.5, "dwell_time": 60.0},
        ]
        deadlines = [500.0, 1000.0]
        metric = analyse_schedule(tiles, t, a, deadlines)
        result = evaluate_schedule_fom(tiles, t, a, deadlines)
        self.assertAlmostEqual(result.fom, metric.fom, places=10)
        self.assertEqual(result.tile_end_times, metric.tile_end_times)
        self.assertEqual(result.cumulative_probs, metric.cdf_cmv_prob)
        self.assertEqual(result.deadlines_full[-1], float("inf"))
        self.assertFalse(math.isnan(result.fom))

    def test_raises_when_total_probability_zero(self) -> None:
        tiles = [
            {"position": np.array([1.0, 0.0, 0.0]), "prob": 0.0, "dwell_time": 10.0},
        ]
        with self.assertRaises(ValueError) as ctx:
            evaluate_schedule_fom(
                tiles,
                telescope=None,
                start_position=None,
                deadlines_finite=[50.0],
            )
        self.assertIn("total tile probability", str(ctx.exception).lower())

    def test_ra_dec_without_position_matches_analyse_schedule(self) -> None:
        """analyse_schedule resolves XYZ from ra/dec; evaluate_schedule_fom must agree."""
        ra, dec = 45.0, 30.0
        x, y, z = ra_dec_to_xyz(ra, dec)
        t = Telescope("t", slew_speed=5.0, dwell_time=10.0)
        start = np.array([1.0, 0.0, 0.0])
        tiles = [
            {"ra": ra, "dec": dec, "prob": 1.0, "dwell_time": 10.0},
        ]
        deadlines = [100.0, 200.0]
        metric = analyse_schedule(tiles, t, start, deadlines)
        result = evaluate_schedule_fom(tiles, t, start, deadlines)
        self.assertAlmostEqual(result.fom, metric.fom, places=10)
        self.assertEqual(len(result.tile_end_times), len(metric.tile_end_times))
        self.assertEqual(result.cumulative_probs, metric.cdf_cmv_prob)


if __name__ == "__main__":
    unittest.main()
