import unittest
import numpy as np
from torch.profiler import schedule

from controllers.schedule_controller import ScheduleController
from controllers.interaction import InteractionController
from models.schedule import Schedule

class DummyRenderer:
    def highlight_selected_tile(self, *args, **kwargs): pass
    def draw_schedule_labels(self, *args, **kwargs): pass
    def draw_schedule_path(self, *args, **kwargs): pass

class TestScheduleControllerWorkflow(unittest.TestCase):
    def setUp(self):
        self.schedule = Schedule()
        self.tiles = [
            {"ra": 10.0, "dec": 20.0, "position": np.array([1.0, 0.0, 0.0]), "prob": 0.4},
            {"ra": 30.0, "dec": 40.0, "position": np.array([0.0, 1.0, 0.0]), "prob": 0.6},
        ]
        self.ctrl = ScheduleController(self.schedule, self.tiles, renderer=None)

    def test_load_From_data_assigns_order_and_dwell(self):
        payload = [
            {"ra": 10.0, "dec": 20.0, "dwell_time": 70.0},
            {"ra": 30.0, "dec": 40.0, "dwell_time": 80.0},
        ]

        def finder(ra, dec):
            for t in self.tiles:
                if t["ra"] == ra and t["dec"] == dec:
                    return t
            return None

        self.ctrl.load_from_data(payload, finder)
        self.assertEqual(len(self.schedule.selected_tiles), 2)
        self.assertEqual(self.schedule.selected_tiles[0]["order"], 1)
        self.assertEqual(self.schedule.selected_tiles[1]["order"], 2)
        self.assertEqual(self.schedule.selected_tiles[0]["dwell_time"], 70.0)

    def test_remove_last_reorders(self):
        self.schedule.selected_tiles.extend(self.tiles)
        self.ctrl._reorder()
        removed = self.ctrl.remove_last()
        self.assertIsNotNone(removed)
        self.assertEqual(len(self.schedule.selected_tiles), 1)
        self.assertEqual(self.schedule.selected_tiles[0]["order"], 1)

class TestInteractionControllerWorkflow(unittest.TestCase):
    def test_find_closest_tile_and_threshold(self):
        tiles = [
            {"position": np.array([1.0, 0.0, 0.0])},
            {"position": np.array([0.0, 1.0, 0.0])},
        ]
        c = InteractionController(
            tiles=tiles,
            schedule=Schedule(),
            renderer=DummyRenderer(),
            max_pick_distance=2.0
        )
        closest = c.find_closest_tile([1.0, 0.1, 0.0])
        self.assertIs(closest, tiles[0])
