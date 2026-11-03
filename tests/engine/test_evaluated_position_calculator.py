"""Tests for Section_each-style EvaluatedPosition aggregation.

Ported from python_calc ``tests/test_evaluated_position_calculator.py`` (commit 270d23b).
"""

import unittest
from math import hypot, pi

from app.engine.calculation.evaluated_position_calculator import EvaluatedPositionCalculator
from app.engine.calculation.rounding import CalculationValueType
from app.engine.calculation.overhead_wire_calculator import OverheadWireCalculator
from app.engine.calculation.pole_assembly import PoleAssembly
from app.engine.calculation.pole_calculator import PoleCalculator
from app.engine.domain.conditions import SeismicCondition, WindCondition
from app.engine.domain.pole import PoleObject
from app.engine.domain.overhead_wire import OverheadWire


class EvaluatedPositionCalculatorTests(unittest.TestCase):
    def setUp(self):
        self.lower = PoleObject(
            name="Lower",
            pole_type="Straight",
            diameter_lower_mm=220,
            diameter_upper_mm=220,
            thickness_lower_mm=6,
            thickness_upper_mm=6,
            material="STK540",
            top_elevation_m=4,
        )
        self.upper = PoleObject(
            name="Upper",
            pole_type="Straight",
            diameter_lower_mm=180,
            diameter_upper_mm=180,
            thickness_lower_mm=5,
            thickness_upper_mm=5,
            material="STK400",
            top_elevation_m=10,
        )
        wind = WindCondition(2, 10)
        seismic = SeismicCondition.ground(0.5)
        self.pole_calculator = PoleCalculator(
            PoleAssembly([self.upper, self.lower]),
            wind,
            seismic,
        )
        self.calculator = EvaluatedPositionCalculator(self.pole_calculator)

    def test_calculates_all_eight_directions_and_exposes_n_for_report(self):
        result = self.calculator.calculate_at(0)

        self.assertEqual(len(result.directional_results), 8)
        self.assertEqual(result.report_result.direction, "N")
        self.assertAlmostEqual(result.report_result.angle_rad, pi / 2)
        self.assertEqual(result.report_result.total_wind_load_x_n, 0)
        self.assertGreater(result.report_result.total_wind_load_y_n, 0)

    def test_uses_material_and_section_properties_at_evaluated_position(self):
        base_result = self.calculator.calculate_at(0)
        joint_result = self.calculator.calculate_at(4)

        self.assertEqual(base_result.evaluated_pole_name, "Lower")
        self.assertEqual(base_result.material_name, "STK540")
        self.assertEqual(
            base_result.report_result.wind_strength.allowable_stress_n_mm2,
            375,
        )
        self.assertEqual(joint_result.evaluated_pole_name, "Upper")
        self.assertEqual(joint_result.material_name, "STK400")
        self.assertEqual(
            joint_result.report_result.wind_strength.allowable_stress_n_mm2,
            235,
        )

    def test_resultant_moment_and_bending_stress(self):
        result = self.calculator.calculate_at(0)
        north = result.report_result
        expected_moment = hypot(
            north.combined_wind_moment_x_nm,
            north.combined_wind_moment_y_nm,
        )

        self.assertAlmostEqual(north.combined_wind_moment_nm, expected_moment)
        self.assertAlmostEqual(
            north.wind_strength.calculated_stress_n_mm2,
            self.calculator.rounding.apply(
                expected_moment
                / result.section_properties.section_modulus_cm3,
                CalculationValueType.STRESS,
            ),
        )

    def test_vba_boundary_rule_marks_utilization_one_as_ng(self):
        strength = self.calculator._strength_result(
            bending_moment_nm=2350,
            section_modulus_cm3=10,
            allowable_stress_n_mm2=235,
        )

        self.assertEqual(strength.utilization_ratio, 1.0)
        self.assertEqual(strength.status, "N.G")

    def test_total_fixload_and_seismic_are_aggregated(self):
        pole = self.pole_calculator.aggregate_at(0)
        result = self.calculator.calculate_at(0)

        self.assertAlmostEqual(result.total_fix_load_n, pole.total_fix_load_n)
        self.assertAlmostEqual(
            result.total_seismic_load_n,
            pole.total_seismic_load_n,
        )
        self.assertAlmostEqual(
            result.total_seismic_moment_nm,
            pole.total_seismic_moment_nm,
        )

    def test_ohw_seismic_tension_is_added_to_directional_resultant(self):
        wire = OverheadWire(
            name="Wire",
            mass_per_length_kg_m=0.2,
            diameter_mm=10,
            elevation_m=3,
            span_length_m=10,
            sag_ratio_percent=3,
            base_wind_coefficient=1,
            fixed_angle_deg=0,
            vertical_angle_deg=0,
        )
        wire_calculator = OverheadWireCalculator(
            [wire],
            self.pole_calculator.wind_condition,
            self.pole_calculator.seismic_condition,
        )
        calculator = EvaluatedPositionCalculator(
            self.pole_calculator,
            overhead_wire_calculator=wire_calculator,
        )

        result = calculator.calculate_at(0)
        wire_result = wire_calculator.aggregate_at(0)

        self.assertAlmostEqual(
            result.report_result.resultant_seismic_load_n,
            result.total_seismic_load_n
            + abs(wire_result.total_seismic_tension_n),
        )


if __name__ == "__main__":
    unittest.main()
