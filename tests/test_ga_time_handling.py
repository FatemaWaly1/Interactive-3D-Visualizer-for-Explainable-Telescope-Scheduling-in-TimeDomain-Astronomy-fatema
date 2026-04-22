import random
import unittest

import numpy as np

from services.ga_scheduler import (
    brute_force_best_order,
    fitness_function,
    run_ga,
    shift_deadlines,
)


class TestGATimeHandling(unittest.TestCase):
    def test_shift_deadlines_clips_at_zero_and_keeps_inf(self):
        deadlines = [100.0, 200.0, float("inf")]

        shifted = shift_deadlines(deadlines, 50.0)
        self.assertEqual(shifted, [50.0, 150.0, float("inf")])

        shifted2 = shift_deadlines(deadlines, 250.0)
        self.assertEqual(shifted2, [0.0, 0.0, float("inf")])

    def test_brute_force_best_order_matches_manual_evaluation(self):
        # Simple 2-tile case; set telescope=None so order only affects cumulative dwell times.
        tiles = [
            {"position": None, "dwell_time": 1.0, "prob": 0.6},
            {"position": None, "dwell_time": 2.0, "prob": 0.4},
        ]
        telescope = None
        start_position = None

        deadlines = [1.5, 3.0, float("inf")]
        merits = [1.0, 0.5, 0.0]

        t_opt = 0.75
        expected_deadlines = shift_deadlines(deadlines, t_opt)

        # Two possible permutations for n=2
        f_order_01 = fitness_function(
            order=[0, 1],
            tiles=tiles,
            telescope=telescope,
            deadlines=expected_deadlines,
            merits=merits,
            start_position=start_position,
        )
        f_order_10 = fitness_function(
            order=[1, 0],
            tiles=tiles,
            telescope=telescope,
            deadlines=expected_deadlines,
            merits=merits,
            start_position=start_position,
        )

        manual_best_order = [0, 1] if f_order_01 >= f_order_10 else [1, 0]

        best_order, best_fom = brute_force_best_order(
            tiles=tiles,
            telescope=telescope,
            deadlines=deadlines,
            merits=merits,
            start_position=start_position,
            t_opt=t_opt,
        )

        self.assertEqual(best_order, manual_best_order)
        self.assertAlmostEqual(best_fom, max(f_order_01, f_order_10), places=12)


class TestRunGA(unittest.TestCase):
    """run_ga: progress_callback wiring and small end-to-end runs."""

    def test_single_tile_returns_trivial_order_without_progress(self):
        calls = []

        def cb(_):
            calls.append(1)

        tiles = [
            {"position": np.array([1.0, 0.0, 0.0]), "dwell_time": 60.0, "prob": 1.0},
        ]
        best, history = run_ga(
            tiles=tiles,
            telescope=None,
            deadlines=[100.0, float("inf")],
            merits=[1.0, 0.0],
            start_position=None,
            n_generations=10,
            pop_size=4,
            time_points=None,
            progress_callback=cb,
        )
        self.assertEqual(best, [0])
        self.assertEqual(history, [])
        self.assertEqual(calls, [])

    def test_progress_callback_fires_each_generation(self):
        random.seed(42)
        calls = []
        tiles = [
            {"position": np.array([1.0, 0.0, 0.0]), "dwell_time": 60.0, "prob": 0.5},
            {"position": np.array([0.0, 1.0, 0.0]), "dwell_time": 60.0, "prob": 0.5},
        ]
        deadlines = [2000.0, float("inf")]
        merits = [1.0, 0.0]
        n_gen = 7

        def cb(payload):
            calls.append(dict(payload))

        best, _hist = run_ga(
            tiles=tiles,
            telescope=None,
            deadlines=deadlines,
            merits=merits,
            start_position=None,
            n_generations=n_gen,
            pop_size=8,
            time_points=None,
            progress_callback=cb,
        )
        self.assertEqual(len(best), 2)
        self.assertEqual(len(calls), n_gen)
        self.assertEqual(calls[0]["generation"], 1)
        self.assertIn("best_fom", calls[0])
        self.assertIn("elapsed_s", calls[0])


if __name__ == "__main__":
    unittest.main()

