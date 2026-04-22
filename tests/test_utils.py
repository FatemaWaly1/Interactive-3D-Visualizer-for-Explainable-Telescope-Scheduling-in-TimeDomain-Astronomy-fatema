import json
import unittest
import os
import sys
import tempfile

from project_utils import load_json_file, viridis_rgb, prob_to_blue_rgb

class TestLoadJsonFile(unittest.TestCase):
    def test_returns_none_for_missing_file(self):
        data = load_json_file("non_Existent_file.json")
        self.assertIsNone(data)

    def test_load_valid_json_file(self):
        payload = {"ra": 10.0, "dec": -0.5, "prob": 0.123}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump(payload, tmp)
            tmp_path = tmp.name

        try:
            loaded = load_json_file(tmp_path)
            self.assertEqual(loaded, payload)
        finally:
            os.remove(tmp_path)

class TestViridisRgb(unittest.TestCase):
    def test_clamps_below_zero_to_first_color(self):
        self.assertEqual(viridis_rgb(-0.1), (68, 1, 84))

    def test_clamps_above_one_to_last_color(self):
        self.assertEqual(viridis_rgb(1.1), (253, 231, 37))

    def test_exact_stop_values(self):
        self.assertEqual(viridis_rgb(0.0), (68, 1, 84))
        self.assertEqual(viridis_rgb(0.25), (59, 82, 139))
        self.assertEqual(viridis_rgb(0.5), (33, 145, 140))
        self.assertEqual(viridis_rgb(0.75), (94, 201, 98))
        self.assertEqual(viridis_rgb(1.0), (253, 231, 37))

    def test_midnight_between_two_stops_by_hand(self):
        # Between 0.0 and 0.25:
        #   t0 = 0.0, c0 = (68, 1, 84)
        #   t1 = 0.25, c1 = (59, 82, 139)
        # At t = 0.125, f = (t - t0) / (t1 - t0) = 0.5
        # r = int(68 + 0.5 * (59 - 68)) = int(63.5) = 63
        # g = int( 1 + 0.5 * (82 -  1)) = int(41.5) = 41
        # b = int(84 + 0.5 * (139 - 84)) = int(111.5) = 111
        expected = (63, 41, 111)
        self.assertEqual(viridis_rgb(0.125), expected)

class TestProbToBlueRgb(unittest.TestCase):
    def test_prob_to_blue_endpoints(self):
        self.assertEqual(prob_to_blue_rgb(0.0), (22, 27, 34))
        self.assertEqual(prob_to_blue_rgb(1.0), (88, 166, 255))

    def test_prob_to_blue_midpoint_by_hand(self):
        # For t = 0.5:
        # r = int(22 + 0.5 * (88 - 22))  = int(22 + 33)   = 55
        # g = int(27 + 0.5 * (166 - 27)) = int(27 + 69.5) = 96
        # b = int(34 + 0.5 * (255 - 34)) = int(34 + 110.5)= 144
        expected = (55, 96, 144)
        self.assertEqual(prob_to_blue_rgb(0.5), expected)

if __name__ == '__main__':
    unittest.main()
