"""Tests for design-standard capability declarations.

Ported from python_calc ``tests/test_design_standard_features.py`` (commit 270d23b).
"""

import unittest
from dataclasses import FrozenInstanceError

from app.engine.domain.standards import (
    CalculationFeatures,
    DesignStandardCode,
    WindCaseMode,
    calculation_features_for,
)


class DesignStandardFeatureTests(unittest.TestCase):
    def test_standards_one_two_and_six_use_confirmed_features(self):
        for code in (
            DesignStandardCode.ACT_DISASTER_PREVENTION,
            DesignStandardCode.FIXED_WIND_DISASTER,
            DesignStandardCode.ACT_TOWER,
        ):
            with self.subTest(code=code):
                features = calculation_features_for(code)
                self.assertIs(features.wind_case_mode, WindCaseMode.OMNI)
                self.assertTrue(features.calculates_bending_stress)
                self.assertTrue(features.calculates_compression_stress)
                self.assertFalse(features.calculates_torque)
                self.assertTrue(features.calculates_seismic_by_default)
                self.assertFalse(features.supports_optional_seismic)
                self.assertFalse(features.supports_oblique_wind)
                self.assertFalse(features.includes_arm_safety_check)

    def test_standards_three_and_four_use_bending_only_by_default(self):
        for code in (
            DesignStandardCode.OLD_LIGHTING_POLE,
            DesignStandardCode.SMALL_SIGN_BOARD,
        ):
            with self.subTest(code=code):
                features = calculation_features_for(code)
                self.assertIs(features.wind_case_mode, WindCaseMode.STRAIGHT)
                self.assertTrue(features.calculates_bending_stress)
                self.assertFalse(features.calculates_compression_stress)
                self.assertFalse(features.calculates_torque)
                self.assertFalse(features.calculates_seismic_by_default)
                self.assertTrue(features.supports_optional_seismic)
                self.assertTrue(features.supports_oblique_wind)
                self.assertEqual(
                    features.includes_arm_safety_check,
                    code is DesignStandardCode.OLD_LIGHTING_POLE,
                )

    def test_standard_five_includes_large_sign_and_arm_features(self):
        features = calculation_features_for(
            DesignStandardCode.LARGE_SIGN_BOARD
        )

        self.assertIs(
            features.wind_case_mode,
            WindCaseMode.STRAIGHT_AND_OBLIQUE,
        )
        self.assertTrue(features.calculates_bending_stress)
        self.assertTrue(features.calculates_compression_stress)
        self.assertTrue(features.calculates_torque)
        self.assertFalse(features.calculates_seismic_by_default)
        self.assertTrue(features.supports_optional_seismic)
        self.assertTrue(features.supports_oblique_wind)
        self.assertTrue(features.includes_arm_safety_check)

    def test_standard_seven_uses_complete_new_jil_features(self):
        features = calculation_features_for(DesignStandardCode.NEW_JIL)

        self.assertIs(
            features.wind_case_mode,
            WindCaseMode.EIGHT_DIRECTIONS,
        )
        self.assertTrue(features.calculates_bending_stress)
        self.assertTrue(features.calculates_compression_stress)
        self.assertTrue(features.calculates_torque)
        self.assertTrue(features.calculates_seismic_by_default)
        self.assertFalse(features.supports_optional_seismic)
        self.assertFalse(features.supports_oblique_wind)
        self.assertTrue(features.includes_arm_safety_check)

    def test_standard_nine_matches_directional_method_without_compression(self):
        new_jil = calculation_features_for(DesignStandardCode.NEW_JIL)
        old_traffic = calculation_features_for(
            DesignStandardCode.OLD_TRAFFIC_SIGNAL
        )

        self.assertEqual(
            old_traffic.wind_case_mode,
            new_jil.wind_case_mode,
        )
        self.assertEqual(
            old_traffic.calculates_bending_stress,
            new_jil.calculates_bending_stress,
        )
        self.assertFalse(old_traffic.calculates_compression_stress)
        self.assertTrue(new_jil.calculates_compression_stress)
        self.assertEqual(
            old_traffic.calculates_torque,
            new_jil.calculates_torque,
        )
        self.assertEqual(
            old_traffic.includes_arm_safety_check,
            new_jil.includes_arm_safety_check,
        )
        self.assertFalse(old_traffic.calculates_seismic_by_default)
        self.assertTrue(old_traffic.supports_optional_seismic)

    def test_haiden_kitei_features_are_not_prepared(self):
        with self.assertRaisesRegex(
            NotImplementedError,
            r"Haiden Kitei.*d_st = 8",
        ):
            calculation_features_for(DesignStandardCode.HAIDEN_KITEI)

    def test_feature_object_is_immutable(self):
        features = calculation_features_for(
            DesignStandardCode.ACT_DISASTER_PREVENTION
        )

        with self.assertRaises(FrozenInstanceError):
            features.calculates_torque = True

    def test_integer_code_can_be_used_for_lookup(self):
        self.assertEqual(
            calculation_features_for(1),
            calculation_features_for(
                DesignStandardCode.ACT_DISASTER_PREVENTION
            ),
        )

    def test_invalid_standard_code_is_rejected(self):
        with self.assertRaises(ValueError):
            calculation_features_for(10)

    def test_feature_dataclass_contains_only_capabilities(self):
        self.assertEqual(
            tuple(CalculationFeatures.__dataclass_fields__),
            (
                "wind_case_mode",
                "calculates_bending_stress",
                "calculates_compression_stress",
                "calculates_torque",
                "calculates_seismic_by_default",
                "supports_optional_seismic",
                "supports_oblique_wind",
                "includes_arm_safety_check",
            ),
        )


if __name__ == "__main__":
    unittest.main()
