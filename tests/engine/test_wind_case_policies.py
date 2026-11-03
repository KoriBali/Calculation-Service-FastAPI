"""Tests for wind-case selection without load calculations.

Ported from python_calc ``tests/test_wind_case_policies.py`` (commit 270d23b).
"""

import unittest
from math import pi

from app.engine.calculation.wind import (
    EightDirectionWindCasePolicy,
    OmniWindCasePolicy,
    StraightObliqueWindCasePolicy,
    StraightWindCasePolicy,
    WindCase,
    wind_case_policy_for,
    wind_cases_for,
)
from app.engine.domain.standards import DesignStandardCode


class WindCaseTests(unittest.TestCase):
    def test_angle_rad_represents_the_same_direct_wind_angle(self):
        wind_case = WindCase(name="N", angle_deg=90.0)

        self.assertAlmostEqual(wind_case.angle_rad, pi * 2 / 4)


class WindCasePolicyTests(unittest.TestCase):
    def test_omni_has_one_representative_case_at_90_degrees(self):
        self.assertEqual(
            OmniWindCasePolicy().cases(),
            (WindCase(name="OMNI", angle_deg=90.0),),
        )

    def test_straight_uses_direct_wind_at_90_degrees(self):
        self.assertEqual(
            StraightWindCasePolicy().cases(),
            (WindCase(name="STRAIGHT", angle_deg=90.0),),
        )

    def test_oblique_is_always_45_degrees(self):
        self.assertEqual(
            StraightObliqueWindCasePolicy().cases(),
            (
                WindCase(name="STRAIGHT", angle_deg=90.0),
                WindCase(name="OBLIQUE", angle_deg=45.0),
            ),
        )

    def test_eight_directions_keep_confirmed_vba_index_order(self):
        cases = EightDirectionWindCasePolicy().cases()

        self.assertEqual(
            tuple(wind_case.name for wind_case in cases),
            ("N", "S", "E", "W", "NE", "SW", "NW", "SE"),
        )
        self.assertEqual(
            tuple(wind_case.angle_deg for wind_case in cases),
            (90.0, 270.0, 0.0, 180.0, 45.0, 225.0, 135.0, 315.0),
        )
        self.assertEqual(
            tuple(wind_case.angle_rad for wind_case in cases),
            (
                pi * 2 / 4,
                pi * 6 / 4,
                pi * 0 / 4,
                pi * 4 / 4,
                pi * 1 / 4,
                pi * 5 / 4,
                pi * 3 / 4,
                pi * 7 / 4,
            ),
        )

    def test_standards_one_two_and_six_select_omni(self):
        for standard in (1, 2, 6):
            with self.subTest(standard=standard):
                self.assertIsInstance(
                    wind_case_policy_for(standard),
                    OmniWindCasePolicy,
                )

    def test_standards_three_and_four_add_oblique_only_when_enabled(self):
        for standard in (3, 4):
            with self.subTest(standard=standard):
                self.assertIsInstance(
                    wind_case_policy_for(standard),
                    StraightWindCasePolicy,
                )
                self.assertIsInstance(
                    wind_case_policy_for(standard, include_oblique=True),
                    StraightObliqueWindCasePolicy,
                )

    def test_standard_five_always_selects_straight_and_oblique(self):
        self.assertIsInstance(
            wind_case_policy_for(5),
            StraightObliqueWindCasePolicy,
        )

    def test_standards_seven_and_nine_select_eight_directions(self):
        for standard in (7, 9):
            with self.subTest(standard=standard):
                self.assertIsInstance(
                    wind_case_policy_for(standard),
                    EightDirectionWindCasePolicy,
                )

    def test_haiden_kitei_remains_unavailable(self):
        with self.assertRaisesRegex(
            NotImplementedError,
            r"Haiden Kitei.*d_st = 8",
        ):
            wind_cases_for(DesignStandardCode.HAIDEN_KITEI)

    def test_invalid_standard_is_rejected(self):
        with self.assertRaises(ValueError):
            wind_cases_for(10)


if __name__ == "__main__":
    unittest.main()
