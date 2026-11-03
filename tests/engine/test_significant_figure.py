"""Tests for VBA-compatible significant-figure rounding.

Ported from python_calc ``tests/test_significant_figure.py`` (commit 270d23b).
"""

import unittest

from app.engine.calculation.significant_figure import SignificantFigureRounder


class SignificantFigureRounderTests(unittest.TestCase):
    def test_rounds_positive_and_negative_values(self):
        round_to_three = SignificantFigureRounder(3)

        self.assertEqual(round_to_three(1234.0), 1230.0)
        self.assertEqual(round_to_three(-1234.0), -1230.0)
        self.assertEqual(round_to_three(0.01234), 0.0123)

    def test_exact_half_uses_even_retained_digit(self):
        round_to_two = SignificantFigureRounder(2)

        self.assertEqual(round_to_two(1.25), 1.2)
        self.assertEqual(round_to_two(1.35), 1.4)
        self.assertEqual(round_to_two(-1.25), -1.2)
        self.assertEqual(round_to_two(-1.35), -1.4)

    def test_non_half_value_uses_normal_nearest_rounding(self):
        round_to_three = SignificantFigureRounder(3)

        self.assertEqual(round_to_three(12.44), 12.4)
        self.assertEqual(round_to_three(12.46), 12.5)

    def test_zero_remains_zero(self):
        self.assertEqual(SignificantFigureRounder(4)(0), 0.0)

    def test_rejects_invalid_significant_figure_count(self):
        for invalid_count in (0, -1, 2.5, True):
            with self.subTest(invalid_count=invalid_count):
                with self.assertRaises(ValueError):
                    SignificantFigureRounder(invalid_count)

    def test_rejects_non_finite_values(self):
        round_to_three = SignificantFigureRounder(3)

        for invalid_value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(invalid_value=invalid_value):
                with self.assertRaises(ValueError):
                    round_to_three(invalid_value)


if __name__ == "__main__":
    unittest.main()
