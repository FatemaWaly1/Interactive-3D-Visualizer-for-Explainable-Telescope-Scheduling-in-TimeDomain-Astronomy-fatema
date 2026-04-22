"""Tests for services.geometry: great-circle angular distance."""
import math
import unittest
import numpy as np

from services.geometry import angdist_vec


class TestAngdistVec(unittest.TestCase):
    def test_identical_vectors_zero_angle(self):
        v = np.array([1.0, 0.0, 0.0])
        self.assertAlmostEqual(angdist_vec(v, v), 0.0, places=6)

    def test_orthogonal_unit_vectors_90_deg(self):
        v1 = np.array([1.0, 0.0, 0.0])
        v2 = np.array([0.0, 1.0, 0.0])
        d_rad = angdist_vec(v1, v2)
        self.assertAlmostEqual(d_rad, math.pi / 2, places=5)
        self.assertAlmostEqual(math.degrees(d_rad), 90.0, places=4)

    def test_opposite_vectors_180_deg(self):
        v1 = np.array([1.0, 0.0, 0.0])
        v2 = np.array([-1.0, 0.0, 0.0])
        d_rad = angdist_vec(v1, v2)
        self.assertAlmostEqual(d_rad, math.pi, places=5)

    def test_tile1_to_tile2_hand_check(self):
        # (288°, 15°) and (0°, 45°): cos(d) ≈ 0.39407 -> d ≈ 1.167 rad
        from models.coordinates import ra_dec_to_xyz
        v1 = np.array(ra_dec_to_xyz(288.0, 15.0))
        v2 = np.array(ra_dec_to_xyz(0.0, 45.0))
        d_rad = angdist_vec(v1, v2)
        # Expected from hand: arccos(0.39407) ≈ 1.167 rad, ≈ 66.8°
        self.assertAlmostEqual(d_rad, math.acos(0.39407), places=3)
        self.assertAlmostEqual(math.degrees(d_rad), 66.8, places=0)

    def test_accepts_lists(self):
        v1 = [1.0, 0.0, 0.0]
        v2 = [0.0, 1.0, 0.0]
        self.assertAlmostEqual(angdist_vec(v1, v2), math.pi / 2, places=5)


if __name__ == "__main__":
    unittest.main()
