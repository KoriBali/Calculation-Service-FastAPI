"""Tests for the confirmed non-concrete d_st 1, 2, and 6 stress policy.

Ported from python_calc ``tests/test_stress_policies.py`` (commit 270d23b).
"""

import unittest
from dataclasses import FrozenInstanceError

from app.engine.calculation.stress import (
    CompressionBendingStressInput,
    CompressionBendingStressPolicy,
    CompressionBendingStressResult,
    LargeSignPoleStressInput,
    LargeSignPoleStressPolicy,
    LargeSignPoleStressResult,
    OldTrafficSignalPoleStressInput,
    OldTrafficSignalPoleStressPolicy,
    OldTrafficSignalPoleStressResult,
    NewJILPoleStressInput,
    NewJILPoleStressPolicy,
    NewJILPoleStressResult,
    SimpleBendingStressInput,
    SimpleBendingStressPolicy,
    SimpleBendingStressResult,
)


def stress_input(**overrides) -> CompressionBendingStressInput:
    values = {
        "total_fix_load_n": 10000,
        "total_seismic_load_n": 4000,
        "total_wind_moment_nm": 5000,
        "total_seismic_moment_nm": 4000,
        "active_pole_segment_lengths_m": (1.0,),
        "cross_section_area_cm2": 20,
        "section_modulus_cm3": 100,
        "radius_of_gyration_cm": 10,
        "short_term_allowable_bending_n_mm2": 235,
    }
    values.update(overrides)
    return CompressionBendingStressInput(**values)


class CompressionBendingStressPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = CompressionBendingStressPolicy()

    def test_wind_case_uses_fixload_only(self):
        result = self.policy.calculate(stress_input())

        self.assertEqual(result.controlling_load_case, "wind")
        self.assertEqual(result.max_total_moment_nm, 5000.0)
        self.assertEqual(result.vertical_load_n, 10000.0)

    def test_seismic_case_adds_half_seismic_load(self):
        result = self.policy.calculate(
            stress_input(
                total_wind_moment_nm=-50000,
                total_seismic_moment_nm=-60000,
            )
        )

        self.assertEqual(result.absolute_total_wind_moment_nm, 50000.0)
        self.assertEqual(result.absolute_total_seismic_moment_nm, 60000.0)
        self.assertEqual(result.max_total_moment_nm, 60000.0)
        self.assertEqual(result.controlling_load_case, "seismic")
        self.assertEqual(result.vertical_load_n, 12000.0)

    def test_equal_absolute_moments_select_seismic_case(self):
        result = self.policy.calculate(
            stress_input(
                total_wind_moment_nm=-5000,
                total_seismic_moment_nm=5000,
            )
        )

        self.assertEqual(result.controlling_load_case, "seismic")
        self.assertEqual(result.vertical_load_n, 12000.0)

    def test_buckling_length_sums_active_segments_in_centimetres(self):
        result = self.policy.calculate(
            stress_input(active_pole_segment_lengths_m=(1.5, 2.5, 6.0))
        )

        self.assertEqual(result.buckling_length_cm, 2000.0)

    def test_low_slenderness_branch_matches_confirmed_sequence(self):
        result = self.policy.calculate(stress_input())

        self.assertEqual(result.slenderness_ratio_lambda, 20.0)
        self.assertEqual(result.limit_slenderness_ratio_lambda, 120.0)
        self.assertEqual(result.safety_factor_nu, 1.52)
        self.assertEqual(result.allowable_compressive_stress_n_mm2, 152.9)
        self.assertEqual(result.compressive_stress_n_mm2, 5.0)
        self.assertEqual(result.bending_stress_n_mm2, 50.0)
        self.assertEqual(result.compression_utilization_ratio, 0.022)
        self.assertEqual(result.bending_utilization_ratio, 0.213)
        self.assertEqual(result.total_utilization_ratio, 0.235)
        self.assertEqual(result.status, "O.K")

    def test_high_slenderness_branch_uses_point_277_formula(self):
        result = self.policy.calculate(
            stress_input(
                total_wind_moment_nm=-50000,
                total_seismic_moment_nm=60000,
                active_pole_segment_lengths_m=(4.0, 6.0),
                radius_of_gyration_cm=5,
            )
        )

        self.assertEqual(result.slenderness_ratio_lambda, 400.0)
        self.assertEqual(result.limit_slenderness_ratio_lambda, 120.0)
        self.assertEqual(result.safety_factor_nu, 8.91)
        self.assertEqual(result.allowable_compressive_stress_n_mm2, 5.9)
        self.assertEqual(result.total_utilization_ratio, 3.231)
        self.assertEqual(result.status, "N.G")

    def test_intermediate_rounding_uses_excel_half_away_from_zero(self):
        result = self.policy.calculate(
            stress_input(
                active_pole_segment_lengths_m=(0.01125,),
                radius_of_gyration_cm=1,
            )
        )

        # Lk = 0.01125 * 2 * 100 = 2.25 cm; Excel ROUND gives 2.3.
        self.assertEqual(result.slenderness_ratio_lambda, 2.3)

    def test_result_is_immutable(self):
        result = self.policy.calculate(stress_input())

        self.assertIsInstance(result, CompressionBendingStressResult)
        with self.assertRaises(FrozenInstanceError):
            result.status = "N.G"

    def test_net_and_arm_are_not_stress_input_fields(self):
        fields = set(CompressionBendingStressInput.__dataclass_fields__)

        self.assertFalse(any("net" in field.lower() for field in fields))
        self.assertFalse(any("arm" in field.lower() for field in fields))

    def test_rejects_invalid_section_and_length_inputs(self):
        invalid_inputs = (
            stress_input(active_pole_segment_lengths_m=()),
            stress_input(active_pole_segment_lengths_m=(1.0, 0.0)),
            stress_input(cross_section_area_cm2=0),
            stress_input(section_modulus_cm3=0),
            stress_input(radius_of_gyration_cm=0),
            stress_input(short_term_allowable_bending_n_mm2=0),
        )
        for calculation_input in invalid_inputs:
            with self.subTest(calculation_input=calculation_input):
                with self.assertRaises(ValueError):
                    self.policy.calculate(calculation_input)


class SimpleBendingStressPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = SimpleBendingStressPolicy()

    def test_first_reference_image_value(self):
        result = self.policy.calculate(
            SimpleBendingStressInput(
                total_moment_nm=2102.0,
                section_modulus_cm3=24.09,
                short_term_allowable_bending_n_mm2=235,
            )
        )

        self.assertEqual(result.bending_stress_n_mm2, 87.3)
        self.assertEqual(result.safety_factor, 0.371)
        self.assertEqual(result.status, "O.K")

    def test_second_reference_image_value(self):
        result = self.policy.calculate(
            SimpleBendingStressInput(
                total_moment_nm=6118.5,
                section_modulus_cm3=62.69,
                short_term_allowable_bending_n_mm2=235,
            )
        )

        self.assertEqual(result.bending_stress_n_mm2, 97.6)
        self.assertEqual(result.safety_factor, 0.415)
        self.assertEqual(result.status, "O.K")

    def test_ohw_reference_uses_final_combined_moment(self):
        result = self.policy.calculate(
            SimpleBendingStressInput(
                total_moment_nm=14015.6,
                section_modulus_cm3=139.22,
                short_term_allowable_bending_n_mm2=235,
            )
        )

        self.assertEqual(result.bending_stress_n_mm2, 100.7)
        self.assertEqual(result.safety_factor, 0.429)
        self.assertEqual(result.status, "O.K")

    def test_moment_is_evaluated_as_an_absolute_magnitude(self):
        positive = self.policy.calculate(
            SimpleBendingStressInput(-2102.0, 24.09, 235)
        )

        self.assertEqual(positive.absolute_total_moment_nm, 2102.0)
        self.assertEqual(positive.bending_stress_n_mm2, 87.3)

    def test_safety_factor_equal_to_one_is_ok(self):
        result = self.policy.calculate(
            SimpleBendingStressInput(
                total_moment_nm=23500,
                section_modulus_cm3=100,
                short_term_allowable_bending_n_mm2=235,
            )
        )

        self.assertEqual(result.safety_factor, 1.0)
        self.assertEqual(result.status, "O.K")

    def test_safety_factor_greater_than_one_is_ng(self):
        result = self.policy.calculate(
            SimpleBendingStressInput(
                total_moment_nm=23560,
                section_modulus_cm3=100,
                short_term_allowable_bending_n_mm2=235,
            )
        )

        self.assertGreater(result.safety_factor, 1.0)
        self.assertEqual(result.status, "N.G")

    def test_result_is_immutable(self):
        result = self.policy.calculate(SimpleBendingStressInput(2102, 24.09, 235))

        self.assertIsInstance(result, SimpleBendingStressResult)
        with self.assertRaises(FrozenInstanceError):
            result.status = "N.G"

    def test_rejects_invalid_allowable_and_section_modulus(self):
        for calculation_input in (
            SimpleBendingStressInput(1000, 0, 235),
            SimpleBendingStressInput(1000, 10, 0),
        ):
            with self.subTest(calculation_input=calculation_input):
                with self.assertRaises(ValueError):
                    self.policy.calculate(calculation_input)


class LargeSignPoleStressPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = LargeSignPoleStressPolicy()

    @staticmethod
    def reference_input(**overrides):
        values = {
            "total_fix_load_n": 3433.1,
            "straight_total_bending_moment_nm": 40431.2,
            "straight_total_torsional_moment_nm": 11192.7,
            "oblique_total_bending_moment_nm": 31922.3,
            "oblique_total_torsional_moment_nm": 5596.4,
            "arm_height_m": 6.05,
            "evaluated_position_m": 0.0,
            "pole_diameter_mm": 216.3,
            "cross_section_area_cm2": 38.36,
            "moment_of_inertia_cm4": 2126.05,
            "section_modulus_cm3": 196.58,
            "radius_of_gyration_cm": 7.44,
            "short_term_allowable_bending_n_mm2": 235,
            "short_term_allowable_shear_n_mm2": 136,
        }
        values.update(overrides)
        return LargeSignPoleStressInput(**values)

    def test_reference_straight_result(self):
        result = self.policy.calculate(self.reference_input())

        self.assertEqual(result.buckling_length_cm, 1210.0)
        self.assertEqual(result.slenderness_ratio_lambda, 162.6)
        self.assertEqual(result.limit_slenderness_ratio_lambda, 120.0)
        self.assertEqual(result.allowable_compressive_stress_n_mm2, 35.5)
        self.assertEqual(result.polar_moment_of_inertia_cm4, 4252.1)
        self.assertEqual(result.straight.wind_direction_deg, 90.0)
        self.assertEqual(result.straight.compressive_stress_n_mm2, 0.89)
        self.assertEqual(result.straight.bending_stress_n_mm2, 205.7)
        self.assertEqual(
            result.straight.combined_compression_bending_stress_n_mm2,
            206.6,
        )
        self.assertEqual(
            result.straight.compression_bending_utilization_ratio,
            0.892,
        )
        self.assertEqual(result.straight.torsional_shear_stress_n_mm2, 28.5)
        self.assertEqual(result.straight.maximum_shear_stress_n_mm2, 107.2)
        self.assertEqual(result.straight.shear_utilization_ratio, 0.788)
        self.assertEqual(result.straight.maximum_combined_stress_n_mm2, 210.5)
        self.assertEqual(result.straight.combined_utilization_ratio, 0.896)
        self.assertEqual(result.straight.combined_status, "O.K")

    def test_reference_oblique_result(self):
        result = self.policy.calculate(self.reference_input())

        self.assertEqual(result.oblique.wind_direction_deg, 45.0)
        self.assertEqual(result.oblique.compressive_stress_n_mm2, 0.89)
        self.assertEqual(result.oblique.bending_stress_n_mm2, 162.4)
        self.assertEqual(
            result.oblique.combined_compression_bending_stress_n_mm2,
            163.3,
        )
        self.assertEqual(
            result.oblique.compression_bending_utilization_ratio,
            0.708,
        )
        self.assertEqual(result.oblique.torsional_shear_stress_n_mm2, 14.2)
        self.assertEqual(result.oblique.maximum_shear_stress_n_mm2, 82.9)
        self.assertEqual(result.oblique.shear_utilization_ratio, 0.61)
        self.assertEqual(result.oblique.maximum_combined_stress_n_mm2, 164.6)
        self.assertEqual(result.oblique.combined_utilization_ratio, 0.7)

    def test_status_uses_strict_less_than_one(self):
        result = self.policy.calculate(
            self.reference_input(
                total_fix_load_n=0,
                straight_total_bending_moment_nm=0,
                straight_total_torsional_moment_nm=157.26,
                short_term_allowable_shear_n_mm2=0.4,
            )
        )

        self.assertEqual(result.straight.shear_utilization_ratio, 1.0)
        self.assertEqual(result.straight.shear_status, "N.G")

    def test_result_is_immutable(self):
        result = self.policy.calculate(self.reference_input())

        self.assertIsInstance(result, LargeSignPoleStressResult)
        with self.assertRaises(FrozenInstanceError):
            result.straight = result.oblique

    def test_rejects_arm_at_or_below_evaluated_position(self):
        for arm_height in (0.0, -1.0):
            with self.subTest(arm_height=arm_height):
                with self.assertRaises(ValueError):
                    self.policy.calculate(
                        self.reference_input(arm_height_m=arm_height)
                    )


class OldTrafficSignalPoleStressPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = OldTrafficSignalPoleStressPolicy()

    @staticmethod
    def calculation_input(**overrides):
        values = {
            "total_bending_moments_nm": (
                12051.5,
                -13000.0,
                9000.0,
                -8000.0,
                10000.0,
                -14000.0,
                11000.0,
                -12500.0,
            ),
            "total_torsional_moments_nm": (0.0,) * 8,
            "pole_diameter_mm": 216.3,
            "moment_of_inertia_cm4": 2126.05,
            "section_modulus_cm3": 92.0,
            "short_term_allowable_bending_n_mm2": 235,
            "short_term_allowable_shear_n_mm2": 136,
        }
        values.update(overrides)
        return OldTrafficSignalPoleStressInput(**values)

    def test_calculates_all_eight_directions_in_confirmed_order(self):
        result = self.policy.calculate(self.calculation_input())

        self.assertEqual(
            tuple(item.wind_case_name for item in result.direction_results),
            ("N", "S", "E", "W", "NE", "SW", "NW", "SE"),
        )
        self.assertEqual(
            tuple(item.wind_direction_deg for item in result.direction_results),
            (90.0, 270.0, 0.0, 180.0, 45.0, 225.0, 135.0, 315.0),
        )

    def test_zero_torsion_reference_follows_vba_equations(self):
        result = self.policy.calculate(self.calculation_input())
        north = result.direction_results[0]

        self.assertEqual(result.polar_moment_of_inertia_cm4, 4252.1)
        self.assertEqual(north.bending_stress_n_mm2, 131.0)
        self.assertEqual(north.torsional_shear_stress_n_mm2, 0.0)
        self.assertEqual(north.maximum_shear_stress_n_mm2, 65.5)
        self.assertEqual(north.maximum_combined_stress_n_mm2, 131.0)
        self.assertEqual(north.bending_status, "O.K")
        self.assertEqual(north.shear_status, "O.K")
        self.assertEqual(north.combined_status, "O.K")

    def test_result_contains_no_report_selection(self):
        fields = set(OldTrafficSignalPoleStressResult.__dataclass_fields__)

        self.assertEqual(
            fields,
            {"polar_moment_of_inertia_cm4", "direction_results"},
        )

    def test_status_boundaries_use_strict_less_than(self):
        result = self.policy.calculate(
            self.calculation_input(
                total_bending_moments_nm=(21620.0,) * 8,
                section_modulus_cm3=92.0,
            )
        )

        self.assertEqual(result.direction_results[0].bending_stress_n_mm2, 235.0)
        self.assertEqual(result.direction_results[0].bending_status, "N.G")

    def test_result_is_immutable(self):
        result = self.policy.calculate(self.calculation_input())

        self.assertIsInstance(result, OldTrafficSignalPoleStressResult)
        with self.assertRaises(FrozenInstanceError):
            result.direction_results = ()

    def test_requires_exactly_eight_moments(self):
        for field, value in (
            ("total_bending_moments_nm", (1.0,) * 7),
            ("total_torsional_moments_nm", (1.0,) * 9),
        ):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    self.policy.calculate(self.calculation_input(**{field: value}))


class NewJILPoleStressPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = NewJILPoleStressPolicy()

    @staticmethod
    def calculation_input(**overrides):
        values = {
            "moments_due_to_fixload_nm": (1560.0,) * 8,
            "combined_wind_moments_nm": (23500.0,) * 8,
            "wind_torsional_moments_nm": (1000.0,) * 8,
            "combined_seismic_moments_nm": (11750.0,) * 8,
            "seismic_torsional_moments_nm": (0.0,) * 8,
            "pole_diameter_mm": 200.0,
            "moment_of_inertia_cm4": 2000.0,
            "section_modulus_cm3": 100.0,
            "allowable_bending_n_mm2": 156.0,
            "short_term_allowable_bending_n_mm2": 235.0,
            "short_term_allowable_shear_n_mm2": 136.0,
        }
        values.update(overrides)
        return NewJILPoleStressInput(**values)

    def test_calculates_fixload_wind_and_seismic_for_eight_directions(self):
        result = self.policy.calculate(self.calculation_input())

        self.assertEqual(len(result.direction_results), 8)
        self.assertEqual(
            tuple(item.wind_case_name for item in result.direction_results),
            ("N", "S", "E", "W", "NE", "SW", "NW", "SE"),
        )
        north = result.direction_results[0]
        self.assertEqual(north.fixload_bending_stress_n_mm2, 15.6)
        self.assertEqual(north.fixload_bending_utilization_ratio, 0.1)
        self.assertEqual(north.wind_bending_stress_n_mm2, 235.0)
        self.assertEqual(north.seismic_bending_stress_n_mm2, 118.0)

    def test_wind_and_seismic_are_independent_results(self):
        result = self.policy.calculate(self.calculation_input())
        north = result.direction_results[0]

        self.assertEqual(north.wind_torsional_shear_stress_n_mm2, 2.5)
        self.assertEqual(north.wind_maximum_shear_stress_n_mm2, 118.0)
        self.assertEqual(north.wind_maximum_combined_stress_n_mm2, 236.0)
        self.assertEqual(north.wind_combined_utilization_ratio, 1.0)
        self.assertEqual(north.wind_combined_status, "N.G")
        self.assertEqual(north.seismic_torsional_shear_stress_n_mm2, 0.0)
        self.assertEqual(north.seismic_maximum_shear_stress_n_mm2, 59.0)
        self.assertEqual(north.seismic_maximum_combined_stress_n_mm2, 118.0)
        self.assertEqual(north.seismic_combined_status, "O.K")

    def test_fixload_uses_fb_not_short_term_sfb(self):
        result = self.policy.calculate(self.calculation_input())
        north = result.direction_results[0]

        self.assertEqual(north.fixload_bending_utilization_ratio, 0.1)
        self.assertEqual(north.fixload_bending_status, "O.K")

    def test_torsional_moments_may_all_be_zero(self):
        result = self.policy.calculate(
            self.calculation_input(
                wind_torsional_moments_nm=(0.0,) * 8,
                seismic_torsional_moments_nm=(0.0,) * 8,
            )
        )

        for direction in result.direction_results:
            self.assertEqual(direction.wind_torsional_shear_stress_n_mm2, 0.0)
            self.assertEqual(direction.seismic_torsional_shear_stress_n_mm2, 0.0)

    def test_uses_three_significant_figures_at_each_new_calculation(self):
        result = self.policy.calculate(
            self.calculation_input(
                combined_wind_moments_nm=(12345.6,) * 8,
                section_modulus_cm3=87.65,
            )
        )

        self.assertEqual(result.direction_results[0].wind_bending_stress_n_mm2, 141.0)

    def test_result_has_no_report_case_selection(self):
        fields = set(NewJILPoleStressResult.__dataclass_fields__)

        self.assertEqual(
            fields,
            {"polar_moment_of_inertia_cm4", "direction_results"},
        )

    def test_result_is_immutable(self):
        result = self.policy.calculate(self.calculation_input())

        self.assertIsInstance(result, NewJILPoleStressResult)
        with self.assertRaises(FrozenInstanceError):
            result.direction_results = ()

    def test_requires_exactly_eight_values_for_every_moment_group(self):
        fields = (
            "moments_due_to_fixload_nm",
            "combined_wind_moments_nm",
            "wind_torsional_moments_nm",
            "combined_seismic_moments_nm",
            "seismic_torsional_moments_nm",
        )
        for field in fields:
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    self.policy.calculate(
                        self.calculation_input(**{field: (0.0,) * 7})
                    )


if __name__ == "__main__":
    unittest.main()
