import random
import unittest
import numpy as np
from models.telescope import Telescope
from services.ga_scheduler import run_ga, fitness_function
from services.schedule_metrics import analyse_schedule, compute_merits_for_deadlines

class TestIntegrationGAScheduleFoM(unittest.TestCase):
    def setUp(self):
        random.seed(42)
        self.tiles =[
            {"position": np.array([1.0, 0.0, 0.0]), "prob": 0.30, "dwell_Time": 60.0},
            {"position": np.array([0.0, 1.0, 0.0]), "prob": 0.25, "dwell_time": 60.0},
            {"position": np.array([0.0, 0.0, 1.0]), "prob": 0.20, "dwell_time": 60.0},
            {"position": np.array([0.707, 0.707, 0.0]), "prob": 0.25, "dwell_time": 60.0},
        ]
        self.telescope = Telescope("T", slew_speed=5.0, dwell_time=60.0)
        self.start_position = np.array([1.0, 0.0, 0.0])
        self.deadlines_full = [300.0, 600.0, float("inf")]
        self.merits = compute_merits_for_deadlines(self.deadlines_full)

    def test_ga_output_order_is_valid_permutation(self):
        best_order, history = run_ga(
            tiles=self.tiles,
            telescope=self.telescope,
            deadlines=self.deadlines_full,
            merits=self.merits,
            start_position=self.start_position,
            n_generations=30,
            pop_size=20,
            time_points=[1, 2]
        )
        self.assertEqual(sorted(best_order), list(range(len(self.tiles))))
        self.assertIsInstance(history, list)

    def test_ga_best_order_fom_matches_schedule_metrics_fom(self):
        best_order, _ = run_ga(
            tiles=self.tiles,
            telescope=self.telescope,
            deadlines=self.deadlines_full,
            merits=self.merits,
            start_position=self.start_position,
            n_generations=30,
            pop_size=20,
            time_points=None
        )
        ordered_tiles = [self.tiles[i] for i in best_order]

        # FoM from GA fitness path
        fom_ga = fitness_function(
            order=list(range(len(ordered_tiles))),
            tiles=ordered_tiles,
            telescope=self.telescope,
            deadlines=self.deadlines_full,
            merits=self.merits,
            start_position=self.start_position,
        )

        # FoM from schedule metrics path (finite deadlines)
        metric = analyse_schedule(
            tiles=ordered_tiles,
            telescope=self.telescope,
            start_position=(1.0, 0.0, 0.0),
            deadlines_finite=[300.60, 600.0]
        )
        self.assertAlmostEqual(metric.fom, fom_ga, places=6)