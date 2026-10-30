"""Domain and calculation tests for Arm_Spec/AO_Each/Arm_Part/Arm_Kmpl.

Ported from python_calc ``tests/test_arm.py`` (commit 270d23b).
"""

import unittest
from math import hypot

from app.engine.calculation.arm_calculator import (
    ArmAssemblyCalculator,
    ArmPartCalculator,
    ArmSpecificationCalculator,
)
from app.engine.domain.arm import (
    Arm,
    ArmAssembly,
    ArmLoadObject,
    ArmObjectType,
    ArmPart,
)
from app.engine.domain.standards import DesignStandardFactory


def standard(code, **options):
    return DesignStandardFactory.create(
        code,
        structure_height_m=10,
        **options,
    )


def sample_arm(height=6.0, fixed_angle=0):
    return Arm(
        name="Arm-1",
        diameter_mm=114.3,
        thickness_mm=3.5,
        total_length_m=1.0,
        exposed_length_m=0.9,
        installation_height_m=height,
        material="STK400",
        fixed_angle_deg=fixed_angle,
    )


def mounted(name, distance):
    return ArmLoadObject(
        name=name,
        object_type="Directional",
        front_area_m2=0.266,
        side_area_m2=0.226,
        mass_per_unit_kg=20,
        horizontal_load_distance_m=distance,
        base_wind_coefficient=1.0,
        quantity=1,
    )


class ArmDomainTests(unittest.TestCase):
    def test_mounted_objects_are_ordered_farthest_to_nearest(self):
        part = ArmPart(
            sample_arm(),
            (mounted("Near", 0.2), mounted("Far", 0.9), mounted("Middle", 0.5)),
        )
        self.assertEqual(
            tuple(item.name for item in part.mounted_objects),
            ("Far", "Middle", "Near"),
        )

    def test_arm_body_cannot_be_supplied_as_mounted_object(self):
        body = ArmLoadObject(
            name="Invalid body",
            object_type=ArmObjectType.ARM_BODY,
            front_area_m2=0.1,
            side_area_m2=0,
            mass_per_unit_kg=1,
            horizontal_load_distance_m=0.5,
            base_wind_coefficient=0.7,
        )
        with self.assertRaisesRegex(ValueError, "generated from Arm"):
            ArmPart(sample_arm(), (body,))

    def test_only_single_round_straight_is_accepted(self):
        with self.assertRaisesRegex(ValueError, "SingleRoundStraight"):
            Arm(**{**sample_arm().__dict__, "arm_type": "Taper"})

    def test_round_arm_shape_factor_is_fixed_and_not_an_input(self):
        arm = sample_arm()
        self.assertEqual(arm.shape_factor, 0.7)
        self.assertNotIn("base_wind_coefficient", arm.__dataclass_fields__)

    def test_mounted_object_has_no_independent_fix_angle_input(self):
        self.assertNotIn("fixed_angle_deg", ArmLoadObject.__dataclass_fields__)


class ArmSpecificationCalculatorTests(unittest.TestCase):
    def test_calculates_round_arm_and_forces_zero_side_area(self):
        result = ArmSpecificationCalculator(standard(3)).calculate(sample_arm())
        self.assertGreater(result.section_area_cm2, 0)
        self.assertGreater(result.section_modulus_cm3, 0)
        self.assertGreater(result.moment_of_inertia_cm4, 0)
        self.assertEqual(
            result.polar_moment_of_inertia_cm4,
            round(result.moment_of_inertia_cm4 * 2, 2),
        )
        self.assertEqual(result.front_projected_area_m2, 0.103)
        self.assertEqual(result.side_projected_area_m2, 0.0)
        self.assertEqual(result.center_length_m, 0.5)

    def test_rejects_standard_without_arm(self):
        with self.assertRaisesRegex(ValueError, "does not use Arm"):
            ArmSpecificationCalculator(standard(4))


class ArmPartCalculatorTests(unittest.TestCase):
    def test_arm_is_object_zero_and_objects_follow_confirmed_order(self):
        result = ArmPartCalculator(standard(3)).calculate(
            ArmPart(sample_arm(), (mounted("Near", 0.2), mounted("Far", 0.9))),
            0,
        )
        self.assertEqual(
            tuple((item.object_index, item.object_name) for item in result.object_results),
            ((0, "Arm-1"), (1, "Far"), (2, "Near")),
        )
        self.assertEqual(result.object_results[0].object_type, "ArmBody")
        self.assertEqual(result.object_results[0].side_wind_load_n, 0.0)
        self.assertEqual(
            result.object_results[1].directional_results[0].angle_of_attack_rad,
            result.object_results[0].directional_results[0].angle_of_attack_rad,
        )

    def test_local_fix_and_wind_moments_form_arm_safety_resultant(self):
        result = ArmPartCalculator(standard(3)).calculate(
            ArmPart(sample_arm(), (mounted("Signal", 0.9),)),
            0,
        )
        expected = round(
            hypot(
                result.total_fix_load_moment_at_arm_support_nm,
                result.total_wind_moment_at_arm_support_nm,
            ),
            1,
        )
        self.assertEqual(result.wind_combination_safety.moment_nm, expected)
        self.assertIsNone(result.fix_load_safety)
        self.assertIsNone(result.seismic_combination_safety)
        self.assertEqual(result.total_seismic_load_n, 0.0)

    def test_new_jil_calculates_seismic_and_all_vba_arm_safety_cases(self):
        result = ArmPartCalculator(standard(7)).calculate(
            ArmPart(sample_arm(), (mounted("Signal", 0.9),)),
            0,
        )
        self.assertGreater(result.total_seismic_load_n, 0)
        self.assertIsNotNone(result.fix_load_safety)
        self.assertIsNotNone(result.seismic_combination_safety)
        self.assertEqual(len(result.object_results[0].directional_results), 8)

    def test_standard_five_calculates_signed_torque_but_no_seismic(self):
        result = ArmPartCalculator(standard(5)).calculate(
            ArmPart(sample_arm(), (mounted("Signal", 0.9),)),
            0,
        )
        straight, oblique = result.object_results[1].directional_results
        self.assertEqual(straight.direction, "STRAIGHT")
        self.assertEqual(oblique.direction, "OBLIQUE")
        self.assertNotEqual(oblique.wind_torque_nm, 0)
        self.assertEqual(oblique.seismic_torque_nm, 0)

    def test_optional_general_seismic_does_not_enable_arm_seismic(self):
        result = ArmPartCalculator(
            standard(9, enable_optional_seismic=True, k_value=0.5)
        ).calculate(
            ArmPart(sample_arm(), (mounted("Signal", 0.9),)),
            0,
        )
        self.assertEqual(result.total_seismic_load_n, 0.0)
        self.assertEqual(result.total_seismic_moment_at_arm_support_nm, 0.0)


class ArmAssemblyCalculatorTests(unittest.TestCase):
    def test_aggregates_only_arms_at_or_above_evaluated_position(self):
        assembly = ArmAssembly(
            (
                ArmPart(sample_arm(6), (mounted("Upper object", 0.9),)),
                ArmPart(sample_arm(2), (mounted("Lower object", 0.8),)),
            )
        )
        result = ArmAssemblyCalculator(assembly, standard(9)).aggregate_at(3)
        self.assertEqual(result.active_arm_count, 1)
        self.assertEqual(result.arm_results[0].installation_height_m, 6)
        self.assertEqual(len(result.directional_totals), 8)

    def test_aggregation_preserves_directional_load_moment_and_torque(self):
        assembly = ArmAssembly(
            (ArmPart(sample_arm(fixed_angle=20), (mounted("Signal", 0.9),)),)
        )
        result = ArmAssemblyCalculator(assembly, standard(7)).aggregate_at(0)
        north = next(item for item in result.directional_totals if item.direction == "N")
        self.assertGreater(result.total_fix_load_n, 0)
        self.assertGreater(result.total_seismic_load_n, 0)
        self.assertNotEqual(north.total_wind_moment_x_nm, 0)
        self.assertNotEqual(north.total_fix_load_moment_x_nm, 0)
        self.assertNotEqual(north.total_wind_torque_nm, 0)


if __name__ == "__main__":
    unittest.main()
