"""Tests for standard-specific seismic load policies.

Ported from python_calc ``tests/test_seismic_policies.py`` (commit 270d23b).
"""

import unittest

from app.engine.calculation.direct_object_calculator import DirectObjectCalculator
from app.engine.calculation.overhead_wire_calculator import OverheadWireCalculator
from app.engine.calculation.pole_assembly import PoleAssembly
from app.engine.calculation.pole_calculator import PoleCalculator
from app.engine.calculation.rounding import CalculationValueType
from app.engine.calculation.seismic import (
    FixLoadCoefficientSeismicPolicy,
    NewJILSeismicPolicy,
    NoSeismicPolicy,
    seismic_policy_for,
)
from app.engine.domain.conditions import SeismicCondition, WindCondition
from app.engine.domain.direct_object import DirectObject
from app.engine.domain.overhead_wire import OverheadWire
from app.engine.domain.loads import OverdesignFactor
from app.engine.domain.pole import PoleObject


class SeismicPolicyTests(unittest.TestCase):
    def test_standards_one_two_and_six_use_fixload_in_newtons(self):
        for standard in (1, 2, 6):
            with self.subTest(standard=standard):
                policy = seismic_policy_for(standard, k_value=0.5)
                self.assertIsInstance(
                    policy,
                    FixLoadCoefficientSeismicPolicy,
                )
                self.assertEqual(
                    policy.calculate_load_n(fix_load_n=1000, mass_kg=25),
                    500.0,
                )

    def test_new_jil_uses_mass_and_confirmed_defaults(self):
        policy = seismic_policy_for(7)

        self.assertIsInstance(policy, NewJILSeismicPolicy)
        self.assertEqual(policy.eqa_m_s2, 4.71)
        self.assertEqual(policy.eqr, 1.0)
        self.assertEqual(
            policy.calculate_load_n(fix_load_n=9999, mass_kg=100),
            471.0,
        )

    def test_new_jil_accepts_input_eqa_and_eqr(self):
        policy = seismic_policy_for(7, eqa_m_s2=5.0, eqr=1.2)

        self.assertEqual(
            policy.calculate_load_n(fix_load_n=9999, mass_kg=100),
            600.0,
        )

    def test_pole_overdesign_affects_fixload_method_and_new_jil_mass(self):
        coefficient = FixLoadCoefficientSeismicPolicy(k_value=0.5)
        new_jil = NewJILSeismicPolicy()
        original_mass = 100.0
        amplified_mass = original_mass * 1.2
        base_fix_load = original_mass * 9.80665
        amplified_fix_load = base_fix_load * 1.2

        self.assertNotEqual(
            coefficient.calculate_load_n(
                fix_load_n=base_fix_load,
                mass_kg=original_mass,
            ),
            coefficient.calculate_load_n(
                fix_load_n=amplified_fix_load,
                mass_kg=original_mass,
            ),
        )
        self.assertNotEqual(
            new_jil.calculate_load_n(
                fix_load_n=base_fix_load,
                mass_kg=original_mass,
            ),
            new_jil.calculate_load_n(
                fix_load_n=amplified_fix_load,
                mass_kg=amplified_mass,
            ),
        )

    def test_optional_seismic_uses_fixload_method(self):
        for standard in (3, 4, 5, 9):
            with self.subTest(standard=standard):
                policy = seismic_policy_for(
                    standard,
                    k_value=0.5,
                    enable_optional_seismic=True,
                )
                self.assertIsInstance(
                    policy,
                    FixLoadCoefficientSeismicPolicy,
                )
                self.assertEqual(
                    policy.calculate_load_n(fix_load_n=1000, mass_kg=25),
                    500.0,
                )

    def test_optional_seismic_requires_k_value(self):
        with self.assertRaisesRegex(ValueError, "k_value"):
            seismic_policy_for(3, enable_optional_seismic=True)

    def test_standards_without_default_seismic_are_explicitly_disabled(self):
        for standard in (3, 4, 5, 9):
            with self.subTest(standard=standard):
                policy = seismic_policy_for(standard, k_value=0.5)
                self.assertIsInstance(policy, NoSeismicPolicy)
                self.assertFalse(policy.enabled)
                self.assertEqual(
                    policy.calculate_load_n(fix_load_n=1000, mass_kg=100),
                    0.0,
                )

    def test_k_value_eqa_and_eqr_validation(self):
        for value in (0, -1, "invalid"):
            with self.subTest(k_value=value):
                with self.assertRaises(ValueError):
                    FixLoadCoefficientSeismicPolicy(value)

        for kwargs in (
            {"eqa_m_s2": 0},
            {"eqa_m_s2": -1},
            {"eqr": 0},
            {"eqr": -1},
            {"eqa_m_s2": "invalid"},
            {"eqr": "invalid"},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    NewJILSeismicPolicy(**kwargs)

    def test_fixload_and_mass_units_are_validated_separately(self):
        coefficient = FixLoadCoefficientSeismicPolicy(0.5)
        new_jil = NewJILSeismicPolicy()

        with self.assertRaisesRegex(ValueError, "fix_load_n"):
            coefficient.calculate_load_n(fix_load_n=-1, mass_kg=100)
        with self.assertRaisesRegex(ValueError, "mass_kg"):
            new_jil.calculate_load_n(fix_load_n=1000, mass_kg=-1)


class CalculatorSeismicPolicyTests(unittest.TestCase):
    def test_new_jil_pole_uses_mass_after_overdesign_factor(self):
        pole = PoleObject(
            name="Pole",
            pole_type="Straight",
            diameter_lower_mm=200,
            diameter_upper_mm=200,
            thickness_lower_mm=5,
            thickness_upper_mm=5,
            material="STK400",
            top_elevation_m=4,
        )
        policy = NewJILSeismicPolicy()
        calculator = PoleCalculator(
            PoleAssembly([pole]),
            WindCondition(2, 4),
            SeismicCondition.ground(0.5),
            overdesign_factor=OverdesignFactor(1.2),
            seismic_policy=policy,
        )

        result = calculator.calculate_one(pole, 0)
        expected = calculator.rounding.apply(
            result.mass_kg * 1.2 * policy.eqa_m_s2 * policy.eqr,
            CalculationValueType.LOAD,
        )
        self.assertEqual(result.seismic_load_n, expected)

    def test_direct_object_has_no_pole_overdesign_factor(self):
        direct_object = DirectObject(
            name="DO",
            object_type="Omni",
            front_area_m2=1,
            side_area_m2=0,
            mass_per_unit_kg=100,
            elevation_m=5,
            base_wind_coefficient=1,
            quantity=1,
            fixed_angle_deg=0,
        )
        calculator = DirectObjectCalculator(
            [direct_object],
            WindCondition(2, 5),
            SeismicCondition.ground(0.5),
        )

        result = calculator.calculate_one(direct_object, 0)
        self.assertEqual(result.fix_load_n, 980.7)
        self.assertEqual(result.seismic_load_n, 490.4)

    def test_ohw_has_no_pole_overdesign_factor(self):
        wire = OverheadWire(
            name="Wire",
            mass_per_length_kg_m=1,
            diameter_mm=10,
            elevation_m=5,
            span_length_m=20,
            sag_ratio_percent=3,
            base_wind_coefficient=1,
            fixed_angle_deg=0,
            vertical_angle_deg=0,
        )
        calculator = OverheadWireCalculator(
            [wire],
            WindCondition(2, 5),
            SeismicCondition.ground(0.5),
        )

        result = calculator.calculate_one(wire, 0)
        self.assertEqual(result.total_mass_kg, 10.0)
        self.assertEqual(result.fix_load_n, 98.1)
        self.assertEqual(result.seismic_load_n, 49.1)

    def test_disabled_standard_returns_zero_seismic_results(self):
        direct_object = DirectObject(
            name="DO",
            object_type="Omni",
            front_area_m2=1,
            side_area_m2=0,
            mass_per_unit_kg=100,
            elevation_m=5,
            base_wind_coefficient=1,
            quantity=1,
            fixed_angle_deg=0,
        )
        calculator = DirectObjectCalculator(
            [direct_object],
            WindCondition(3, 5),
            SeismicCondition.ground(0.5),
        )

        result = calculator.calculate_one(direct_object, 0)
        self.assertFalse(calculator.seismic_policy.enabled)
        self.assertEqual(result.seismic_load_n, 0.0)
        self.assertEqual(result.seismic_moment_nm, 0.0)

    def test_optional_seismic_can_be_enabled_in_calculator(self):
        direct_object = DirectObject(
            name="DO",
            object_type="Omni",
            front_area_m2=1,
            side_area_m2=0,
            mass_per_unit_kg=100,
            elevation_m=5,
            base_wind_coefficient=1,
            quantity=1,
            fixed_angle_deg=0,
        )
        calculator = DirectObjectCalculator(
            [direct_object],
            WindCondition(3, 5),
            SeismicCondition.ground(0.5),
            enable_optional_seismic=True,
        )

        result = calculator.calculate_one(direct_object, 0)
        self.assertTrue(calculator.seismic_policy.enabled)
        self.assertEqual(result.seismic_load_n, 490.4)


if __name__ == "__main__":
    unittest.main()
