"""Tests for standard-specific wind-pressure policies.

Ported from python_calc ``tests/test_wind_pressure_policies.py`` (commit 270d23b).
"""

import unittest

from app.engine.calculation.wind import (
    ActTowerWindPressurePolicy,
    ActWindPressurePolicy,
    FixedWindPressurePolicy,
    HaidenKiteiWindPressurePolicy,
    act_common_parameters,
    calculate_kz,
    wind_pressure_policy_for,
)
from app.engine.domain.conditions import WindCondition


class ActCommonParameterTests(unittest.TestCase):
    def test_er_uses_zb_at_or_below_zb_and_height_above_zb(self):
        at_zb = act_common_parameters(4, 10)
        above_zb = act_common_parameters(4, 20)

        self.assertEqual(at_zb["Er"], round(1.7 * (10 / 550) ** 0.27, 3))
        self.assertEqual(
            above_zb["Er"],
            round(1.7 * (20 / 550) ** 0.27, 3),
        )

    def test_gf_structure_height_boundaries_follow_existing_rule(self):
        self.assertEqual(act_common_parameters(2, 10)["Gf"], 2.2)
        self.assertEqual(act_common_parameters(2, 40)["Gf"], 2.0)

    def test_all_area_density_codes_have_confirmed_zg_and_alpha(self):
        expected = {
            1: (250.0, 0.1),
            2: (350.0, 0.15),
            3: (450.0, 0.2),
            4: (550.0, 0.27),
        }
        for code, (zg, alpha) in expected.items():
            with self.subTest(code=code):
                common = act_common_parameters(code, 40)
                self.assertEqual(common["zg"], zg)
                self.assertEqual(common["alpha"], alpha)

    def test_kz_boundaries_and_each_top_elevation(self):
        self.assertEqual(calculate_kz(5, 5, 5, 0.15), 1.0)
        self.assertEqual(
            calculate_kz(5, 40, 5, 0.15),
            round((5 / 40) ** (2 * 0.15), 3),
        )
        self.assertEqual(
            calculate_kz(27, 40, 5, 0.15),
            round((27 / 40) ** (2 * 0.15), 3),
        )
        self.assertNotEqual(
            calculate_kz(10, 40, 5, 0.15),
            calculate_kz(27, 40, 5, 0.15),
        )


class WindPressurePolicyTests(unittest.TestCase):
    def test_act_pressure_matches_current_python_reference(self):
        policy = ActWindPressurePolicy(8.15, 2, 60)

        self.assertEqual(policy.wind_pressure_at(8.15), 4443.12)

    def test_fixed_pressure_for_each_confirmed_standard(self):
        expected = {
            2: 2214.0,
            3: 2214.0,
            4: 984.0,
            5: 1537.5,
            7: 2214.0,
            9: 2214.0,
        }
        for standard, pressure in expected.items():
            with self.subTest(standard=standard):
                policy = wind_pressure_policy_for(
                    standard,
                    structure_height_m=10,
                )
                self.assertIsInstance(policy, FixedWindPressurePolicy)
                self.assertEqual(policy.wind_pressure_at(10), pressure)

    def test_configurable_standards_use_input_wind_speed(self):
        input_speed_by_standard = {
            3: 50.0,
            4: 50.0,
            5: 40.0,
            7: 40.0,
            9: 50.0,
        }
        expected_pressure = {
            3: 1537.5,
            4: 1537.5,
            5: 984.0,
            7: 984.0,
            9: 1537.5,
        }
        for standard, wind_speed in input_speed_by_standard.items():
            with self.subTest(standard=standard):
                policy = wind_pressure_policy_for(
                    standard,
                    structure_height_m=10,
                    basic_wind_speed_m_s=wind_speed,
                )
                self.assertEqual(policy.wind_speed_m_s, wind_speed)
                self.assertEqual(
                    policy.wind_pressure_at(10),
                    expected_pressure[standard],
                )

    def test_standard_two_keeps_fixed_60_m_s(self):
        policy = wind_pressure_policy_for(
            2,
            structure_height_m=10,
            basic_wind_speed_m_s=40,
        )

        self.assertEqual(policy.wind_speed_m_s, 60.0)
        self.assertEqual(policy.wind_pressure_at(10), 2214.0)

    def test_configurable_standards_use_defaults_when_input_is_absent(self):
        expected_speed = {3: 60.0, 4: 40.0, 5: 50.0, 7: 60.0, 9: 60.0}

        for standard, wind_speed in expected_speed.items():
            with self.subTest(standard=standard):
                policy = wind_pressure_policy_for(
                    standard,
                    structure_height_m=10,
                )
                self.assertEqual(policy.wind_speed_m_s, wind_speed)

    def test_tower_pressure_uses_kz_factor_and_minimum(self):
        minimum_policy = ActTowerWindPressurePolicy(40, 2, 1)
        calculated_policy = ActTowerWindPressurePolicy(8.15, 2, 60)

        self.assertEqual(minimum_policy.wind_pressure_at(10), 2350.0)
        expected = round(
            round(0.6 * calculated_policy.common_parameters["Ds_air"] * 60**2, 3)
            * 1.42
            * calculated_policy.kz_at(8.15),
            3,
        )
        self.assertEqual(calculated_policy.wind_pressure_at(8.15), expected)

    def test_factory_selects_act_and_tower_policies(self):
        inputs = {
            "structure_height_m": 40,
            "area_density_code": 2,
            "basic_wind_speed_m_s": 60,
        }

        self.assertIsInstance(
            wind_pressure_policy_for(1, **inputs),
            ActWindPressurePolicy,
        )
        self.assertIsInstance(
            wind_pressure_policy_for(6, **inputs),
            ActTowerWindPressurePolicy,
        )

    def test_area_density_code_is_required_only_for_act_standards(self):
        for standard in (1, 6):
            with self.subTest(standard=standard):
                with self.assertRaisesRegex(ValueError, "Area Density Code"):
                    wind_pressure_policy_for(
                        standard,
                        structure_height_m=10,
                        basic_wind_speed_m_s=60,
                    )

        self.assertEqual(
            wind_pressure_policy_for(
                3,
                structure_height_m=10,
            ).wind_pressure_at(10),
            2214.0,
        )

    def test_structure_height_must_be_positive_for_every_standard(self):
        for standard in (1, 2, 6, 7, 8, 9):
            with self.subTest(standard=standard):
                with self.assertRaisesRegex(ValueError, "Structure height"):
                    wind_pressure_policy_for(
                        standard,
                        structure_height_m=0,
                        area_density_code=2,
                        basic_wind_speed_m_s=60,
                    )

    def test_haiden_kitei_is_an_explicit_unavailable_placeholder(self):
        policy = wind_pressure_policy_for(8, structure_height_m=10)

        self.assertIsInstance(policy, HaidenKiteiWindPressurePolicy)
        with self.assertRaisesRegex(
            NotImplementedError,
            r"Haiden Kitei.*d_st = 8",
        ):
            policy.wind_pressure_at(10)

    def test_wind_condition_delegates_to_selected_policy(self):
        condition = WindCondition(9, 10)

        self.assertIsInstance(
            condition._pressure_policy,
            FixedWindPressurePolicy,
        )
        self.assertEqual(condition.wind_pressure_at(10), 2214.0)
        self.assertEqual(condition.kz_at(10), 1.0)
        self.assertIsNone(condition.common_parameters)

    def test_wind_condition_passes_optional_wind_speed_to_policy(self):
        condition = WindCondition(
            design_standard=4,
            structure_height_m=10,
            basic_wind_speed_m_s=50,
        )

        self.assertEqual(condition.wind_pressure_at(10), 1537.5)


if __name__ == "__main__":
    unittest.main()
