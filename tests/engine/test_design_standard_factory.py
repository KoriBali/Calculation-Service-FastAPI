"""Tests for complete design-standard policy configuration.

Ported from python_calc ``tests/test_design_standard_factory.py`` (commit 270d23b).
"""

import unittest
from dataclasses import FrozenInstanceError

from app.engine.calculation.rounding import (
    DecimalRoundingPolicy,
    SignificantFigureRoundingPolicy,
)
from app.engine.calculation.seismic import (
    FixLoadCoefficientSeismicPolicy,
    NewJILSeismicPolicy,
    NoSeismicPolicy,
)
from app.engine.calculation.stress import (
    CompressionBendingStressPolicy,
    LargeSignPoleStressPolicy,
    NewJILPoleStressPolicy,
    OldTrafficSignalPoleStressPolicy,
    SimpleBendingStressPolicy,
)
from app.engine.calculation.wind import (
    ActTowerWindPressurePolicy,
    ActWindPressurePolicy,
    EightDirectionWindCasePolicy,
    FixedWindPressurePolicy,
    OmniWindCasePolicy,
    StraightObliqueWindCasePolicy,
    StraightWindCasePolicy,
)
from app.engine.domain.standards import (
    DesignStandard,
    DesignStandardCode,
    DesignStandardFactory,
)


def create_standard(code, **overrides):
    arguments = {"structure_height_m": 10.0}
    if code in (1, 6):
        arguments.update(
            area_density_code=2,
            basic_wind_speed_m_s=40.0,
            k_value=0.5,
        )
    elif code == 2:
        arguments["k_value"] = 0.5
    arguments.update(overrides)
    return DesignStandardFactory.create(code, **arguments)


class DesignStandardFactoryTests(unittest.TestCase):
    def test_factory_maps_every_available_standard_explicitly(self):
        expected = {
            1: (
                ActWindPressurePolicy,
                OmniWindCasePolicy,
                FixLoadCoefficientSeismicPolicy,
                CompressionBendingStressPolicy,
                DecimalRoundingPolicy,
            ),
            2: (
                FixedWindPressurePolicy,
                OmniWindCasePolicy,
                FixLoadCoefficientSeismicPolicy,
                CompressionBendingStressPolicy,
                DecimalRoundingPolicy,
            ),
            3: (
                FixedWindPressurePolicy,
                StraightWindCasePolicy,
                NoSeismicPolicy,
                SimpleBendingStressPolicy,
                DecimalRoundingPolicy,
            ),
            4: (
                FixedWindPressurePolicy,
                StraightWindCasePolicy,
                NoSeismicPolicy,
                SimpleBendingStressPolicy,
                DecimalRoundingPolicy,
            ),
            5: (
                FixedWindPressurePolicy,
                StraightObliqueWindCasePolicy,
                NoSeismicPolicy,
                LargeSignPoleStressPolicy,
                DecimalRoundingPolicy,
            ),
            6: (
                ActTowerWindPressurePolicy,
                OmniWindCasePolicy,
                FixLoadCoefficientSeismicPolicy,
                CompressionBendingStressPolicy,
                DecimalRoundingPolicy,
            ),
            7: (
                FixedWindPressurePolicy,
                EightDirectionWindCasePolicy,
                NewJILSeismicPolicy,
                NewJILPoleStressPolicy,
                SignificantFigureRoundingPolicy,
            ),
            9: (
                FixedWindPressurePolicy,
                EightDirectionWindCasePolicy,
                NoSeismicPolicy,
                OldTrafficSignalPoleStressPolicy,
                DecimalRoundingPolicy,
            ),
        }

        for code, policy_types in expected.items():
            with self.subTest(code=code):
                standard = create_standard(code)
                self.assertIsInstance(standard, DesignStandard)
                self.assertEqual(standard.code, DesignStandardCode(code))
                self.assertIsInstance(
                    standard.wind_pressure_policy, policy_types[0]
                )
                self.assertIsInstance(standard.wind_case_policy, policy_types[1])
                self.assertIsInstance(standard.seismic_policy, policy_types[2])
                self.assertIsInstance(standard.stress_policy, policy_types[3])
                self.assertIsInstance(standard.rounding_policy, policy_types[4])

    def test_standard_object_is_immutable(self):
        standard = create_standard(7)

        with self.assertRaises(FrozenInstanceError):
            standard.name = "Changed"

    def test_standard_names_are_explicit_and_nonempty(self):
        for code in (1, 2, 3, 4, 5, 6, 7, 9):
            with self.subTest(code=code):
                self.assertTrue(create_standard(code).name)

    def test_haiden_kitei_has_clear_unavailable_alert(self):
        with self.assertRaisesRegex(NotImplementedError, "Haiden Kitei"):
            DesignStandardFactory.create(8)

    def test_invalid_code_is_rejected(self):
        for code in (0, 10, 99):
            with self.subTest(code=code):
                with self.assertRaises(ValueError):
                    DesignStandardFactory.create(code)

    def test_height_is_required_without_silent_default(self):
        with self.assertRaisesRegex(ValueError, "structure_height_m"):
            DesignStandardFactory.create(3)

    def test_optional_seismic_is_explicit(self):
        disabled = create_standard(9)
        enabled = create_standard(
            9,
            enable_optional_seismic=True,
            k_value=0.4,
        )

        self.assertIsInstance(disabled.seismic_policy, NoSeismicPolicy)
        self.assertIsInstance(
            enabled.seismic_policy,
            FixLoadCoefficientSeismicPolicy,
        )

    def test_standard_three_can_explicitly_add_oblique_case(self):
        standard = create_standard(3, include_oblique=True)

        self.assertIsInstance(
            standard.wind_case_policy,
            StraightObliqueWindCasePolicy,
        )

    def test_configurable_wind_speed_reaches_pressure_policy(self):
        standard = create_standard(5, basic_wind_speed_m_s=55.0)

        self.assertEqual(standard.wind_pressure_policy.wind_speed_m_s, 55.0)


if __name__ == "__main__":
    unittest.main()
