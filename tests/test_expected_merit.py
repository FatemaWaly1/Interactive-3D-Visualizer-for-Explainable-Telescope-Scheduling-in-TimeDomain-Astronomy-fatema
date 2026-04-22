"""Unit tests for services.expected_merit.expected_FoM."""

import math
import unittest

from services.expected_merit import expected_FoM


class TestExpectedFoM(unittest.TestCase):
    """Tests for the expected_FoM helper."""

    def test_single_deadline_all_early_full_merit(self):
        """If detection always occurs before the first deadline, FoM equals M1."""
        deadlines = [100.0]
        merits = [1.0]

        def cdf(t: float) -> float:
            # Always detected before any positive time
            return 0.0 if t < 0.0 else 1.0

        value = expected_FoM(deadlines, merits, cdf)
        self.assertAlmostEqual(value, 1.0, places=9)

    def test_all_detection_after_last_deadline_zero_merit(self):
        """If all probability is after the last finite deadline with merit 0, FoM is 0."""
        deadlines = [100.0, float("inf")]
        merits = [1.0, 0.0]

        def cdf(t: float) -> float:
            # No detection before 100s; detection happens only after 100s
            if t <= 100.0:
                return 0.0
            return 1.0

        value = expected_FoM(deadlines, merits, cdf)
        # First band has probability 0, second band has probability 1 but merit 0
        self.assertAlmostEqual(value, 0.0, places=9)

    def test_uniform_three_bands_example(self):
        """Uniform detection time on [0, 300] across three bands with paper-like merits."""
        deadlines = [100.0, 200.0, 300.0, float("inf")]
        merits = [1.0, 0.5, 0.1, 0.0]

        def cdf(t: float) -> float:
            # Uniform in [0, 300]
            if t <= 0.0:
                return 0.0
            if t >= 300.0:
                return 1.0
            return t / 300.0

        value = expected_FoM(deadlines, merits, cdf)

        # Each of the first three 100s intervals has probability 1/3
        expected = (1.0 + 0.5 + 0.1) / 3.0
        self.assertAlmostEqual(value, expected, places=9)

    def test_zero_probability_band(self):
        """A band with zero probability should not affect the FoM."""
        deadlines = [100.0, 200.0, float("inf")]
        merits = [1.0, 0.5, 0.0]

        def cdf(t: float) -> float:
            # 50% chance by 100; flat at 0.5 through 200 (so band (100,200] has prob 0); then 1.0
            if t < 100.0:
                return 0.0
            if t <= 200.0:
                return 0.5
            return 1.0

        value = expected_FoM(deadlines, merits, cdf)
        # Band 1: prob 0.5, merit 1.0; band 2: prob 0, merit 0.5; band 3: prob 0.5, merit 0
        expected = 1.0 * 0.5 + 0.5 * 0.0 + 0.0 * 0.5
        self.assertAlmostEqual(value, expected, places=9)

    def test_mismatched_lengths_raises(self):
        """deadlines and merits of different lengths should raise ValueError."""
        deadlines = [100.0, 200.0]
        merits = [1.0]  # too short

        def cdf(t: float) -> float:
            return 0.0

        with self.assertRaises(ValueError):
            expected_FoM(deadlines, merits, cdf)

    def test_non_increasing_deadlines_raises(self):
        """Non-increasing deadlines (D_i < D_{i-1}) should raise ValueError."""
        deadlines = [100.0, 80.0]  # decreasing
        merits = [1.0, 0.5]

        def cdf(t: float) -> float:
            return 0.0

        with self.assertRaises(ValueError):
            expected_FoM(deadlines, merits, cdf)

    def test_decreasing_cdf_raises(self):
        """A CDF that goes down between deadlines should raise ValueError."""
        deadlines = [1.0, 2.0]
        merits = [1.0, 0.5]

        # This CDF is invalid: F(2) < F(1)
        def cdf(t: float) -> float:
            if t <= 1.0:
                return 0.8
            return 0.3

        with self.assertRaises(ValueError):
            expected_FoM(deadlines, merits, cdf)


if __name__ == "__main__":
    unittest.main()

