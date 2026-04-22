"""Tests for models.coordinates: RA/Dec <-> xyz and 3D distance."""
import math
import unittest
import numpy as np

from models.coordinates import ra_dec_to_xyz, calculate_distance_3d


class TestRaDecToXyz(unittest.TestCase):
    def test_ra0_dec45_unit_sphere(self):
        # RA=0°, Dec=45° -> x=cos(45°)cos(0), y=cos(45°)sin(0), z=sin(45°)
        # cos(π/4)=sin(π/4)=√2/2 =approx 0.7071
        x, y, z = ra_dec_to_xyz(0.0, 45.0)
        self.assertAlmostEqual(x, math.sqrt(0.5), places=5)
        self.assertAlmostEqual(y, 0.0, places=5)
        self.assertAlmostEqual(z, math.sqrt(0.5), places=5)

    def test_ra36_dec45(self):
        # Hand-check: Dec 45° -> cos(dec)=sin(dec)=0.7071; RA 36° -> cos(36°), sin(36°)
        x, y, z = ra_dec_to_xyz(36.0, 45.0)
        dec_rad = math.radians(45.0)
        ra_rad = math.radians(36.0)
        expected_x = math.cos(dec_rad) * math.cos(ra_rad)
        expected_y = math.cos(dec_rad) * math.sin(ra_rad)
        expected_z = math.sin(dec_rad)
        self.assertAlmostEqual(x, expected_x, places=5)
        self.assertAlmostEqual(y, expected_y, places=5)
        self.assertAlmostEqual(z, expected_z, places=5)

    def test_unit_sphere_norm(self):
        # Any (ra, dec) should yield a unit vector
        for ra, dec in [(0, 0), (90, 0), (180, -30), (288, 15)]:
            x, y, z = ra_dec_to_xyz(ra, dec)
            norm_sq = x * x + y * y + z * z
            self.assertAlmostEqual(norm_sq, 1.0, places=5)


class TestCalculateDistance3d(unittest.TestCase):
    def test_same_point_zero_distance(self):
        p = (1.0, 0.0, 0.0)
        self.assertAlmostEqual(calculate_distance_3d(p, p), 0.0, places=6)

    def test_orthogonal_unit_vectors(self):
        # (1,0,0) and (0,1,0) -> Euclidean distance = √2
        p1 = np.array([1.0, 0.0, 0.0])
        p2 = np.array([0.0, 1.0, 0.0])
        self.assertAlmostEqual(calculate_distance_3d(p1, p2), math.sqrt(2.0), places=6)

    def test_accepts_tuple_or_array(self):
        p1 = (1.0, 0.0, 0.0)
        p2 = [0.0, 0.0, 1.0]
        self.assertAlmostEqual(calculate_distance_3d(p1, p2), math.sqrt(2.0), places=6)


if __name__ == "__main__":
    unittest.main()
