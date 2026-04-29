import unittest
import numpy as np
from visualisation.sphere_renderer import SphereRenderer

class TestSphereRendererMath(unittest.TestCase):
    def test_slerp_between_orthogonal_unit_vectors(self):
        renderer = SphereRenderer()

        v1 = np.array([1.0, 0.0, 0.0])
        v2 = np.array([0.0, 1.0, 0.0])

        # Request 3pts: start, middle, end
        pts = renderer._slerp_points(v1, v2, n=3)

        self.assertEqual(pts.shape, (3,3))

        # 1st & last col should be ~ v1 & v2 on the unit sphere
        self.assertTrue(np.allclose(pts[0], v1 / np.linalg.norm(v1), atol=1e-6))
        self.assertTrue(np.allclose(pts[-1], v2 / np.linalg.norm(v2), atol=1e-6))

        # Mid pt should be at 45 deg: (sqrt(1/2), sqrt(1/2), 0)
        expected_mid = np.array([np.sqrt(0.5), np.sqrt(0.5), 0.0])
        self.assertTrue(np.allclose(pts[1], expected_mid, atol=1e-6))

        # All pts should lie on the unit sphere
        norms = np.linalg.norm(pts, axis=1)
        self.assertTrue(np.allclose(norms, 1.0, atol=1e-6))


if __name__ == '__main__':
    unittest.main()
