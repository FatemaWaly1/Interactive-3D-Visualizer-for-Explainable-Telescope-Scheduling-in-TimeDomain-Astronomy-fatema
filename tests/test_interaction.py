import unittest
import numpy as np
from controllers.interaction import InteractionController

class TestInteractionController(unittest.TestCase):
    def setUp(self):

        # Two tiles on orthogonal unit vectors
        self.tiles = [
            {"position": np.array([1.0, 0.0, 0.0])},
            {"position": np.array([0.0, 1.0, 0.0])}
        ]

        # For find_closest_tile we can pass None fo schedule/rendere
        self.controller = InteractionController(
            tiles=self.tiles,
            schedule=None,
            renderer=None,
            max_pick_distance=2.0
        )

    def test_find_closest_tile_returns_nearest_within_threshold(self):
        clicked = np.array([1.0, 0.1, 0.0])
        closest = self.controller.find_closest_tile(clicked)

        self.assertIsNotNone(closest)
        self.assertIs(closest, self.tiles[0])

    def test_find_closest_tile_returns_none_when_too_far(self):
        controller = InteractionController(
            tiles=self.tiles,
            schedule=None,
            renderer=None,
            max_pick_distance=0.1
        )

        clicked = np.array([10.0, 10.0, 10.0])
        closest = controller.find_closest_tile(clicked)

        self.assertIsNone(closest)

if __name__ == '__main__':
    unittest.main()
