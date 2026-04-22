import unittest
import numpy as np
from models.telescope import Telescope
from services.schedule_metrics import analyse_schedule

class TestScenarioCompareWorkflow(unittest.TestCase):
    def setUp(self):
        self.telescope = Telescope("T", slew_speed=5.0, dwell_time=60.0)
        self.start_position = (1.0, 0.0, 0.0)
        self.deadlines_finite = [120.0, 300.0]
        self.tiles_a = [
            {"position": np.array([1.0, 0.0, 0.0]), "prob": 0.4, "dwell_time": 60.0},
            {"position": np.array([0.0, 1.0, 0.0]), "prob": 0.6, "dwell_time": 60.0},
        ]
        self.tiles_b = [
            {"position": np.array([0.0, 1.0, 0.0]), "prob": 0.6, "dwell_time": 60.0},
            {"position": np.array([1.0, 0.0, 0.0]), "prob": 0.4, "dwell_time": 60.0},
        ]

    def test_compare_two_schedules_returns_valid_metrics(self):
        a = analyse_schedule(self.tiles_a, self.telescope, self.start_position, self.deadlines_finite)
        b = analyse_schedule(self.tiles_b, self.telescope, self.start_position, self.deadlines_finite)

        # basic contract checks used by scenario dialog
        self.assertEqual(len(a.cdf_times), len(self.tiles_a))
        self.assertEqual(len(b.cdf_times), len(self.tiles_b))
        self.assertEqual(len(a.late_counts_by_deadline), len(self.deadlines_finite))
        self.assertEqual(len(b.cdf_at_deadlines), len(self.deadlines_finite))
        self.assertGreaterEqual(a.fom, 0.0)
        self.assertGreaterEqual(b.fom, 0.0)

    def test_deadline_ordering_in_outputs_is_preserved(self):
        a = analyse_schedule(self.tiles_a, self.telescope, self.start_position, self.deadlines_finite)
        out_deadlines = [d for d, _ in a.cdf_at_deadlines]
        self.assertEqual(out_deadlines, self.deadlines_finite)
