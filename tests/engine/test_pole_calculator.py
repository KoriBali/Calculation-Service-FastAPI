"""Integration tests for the Pole calculation flow.

Ported from python_calc ``tests/test_pole_calculator.py`` (commit 270d23b).
"""

import unittest

from app.engine.calculation.pole_assembly import PoleAssembly
from app.engine.calculation.pole_calculator import PoleCalculator
from app.engine.calculation.rounding import CalculationValueType
from app.engine.domain.conditions import SeismicCondition, WindCondition
from app.engine.domain.loads import OverdesignFactor
from app.engine.domain.pole import PoleObject


class PoleCalculatorTests(unittest.TestCase):
    def setUp(self):
        self.pole = PoleObject(
            name="P1",
            pole_type="Straight",
            diameter_lower_mm=200,
            diameter_upper_mm=200,
            thickness_lower_mm=5,
            thickness_upper_mm=5,
            material="STK400",
            top_elevation_m=4,
        )
        self.calculator = PoleCalculator(
            assembly=PoleAssembly([self.pole]),
            wind_condition=WindCondition(2, 4),
            seismic_condition=SeismicCondition.ground(0.5),
        )

    def test_complete_pole_result(self):
        result = self.calculator.calculate_one(self.pole, 0)

        self.assertEqual(result.geometry.active_length_m, 4)
        self.assertEqual(result.nnc, 0.7)
        self.assertEqual(result.cf, 0.7)
        self.assertEqual(result.wind_pressure_n_m2, 2214.0)
        self.assertEqual(result.projected_area_m2, 0.8)
        self.assertEqual(
            result.seismic_load_n,
            self.calculator.rounding.apply(
                result.fix_load_n * 0.5,
                CalculationValueType.LOAD,
            ),
        )
        self.assertEqual(
            result.wind_moment_nm,
            self.calculator.rounding.apply(
                result.wind_load_n * 2,
                CalculationValueType.MOMENT,
            ),
        )
        self.assertEqual(len(result.directional_results), 8)
        self.assertEqual(result.overdesign_factor, 1.0)

    def test_act_straight_pole_rounds_unit_weight_before_length(self):
        pole = PoleObject(
            name="PDF Pole-1",
            pole_type="Straight",
            diameter_lower_mm=165.2,
            diameter_upper_mm=165.2,
            thickness_lower_mm=4.5,
            thickness_upper_mm=4.5,
            material="STK400",
            top_elevation_m=14.84,
        )
        calculator = PoleCalculator(
            assembly=PoleAssembly([pole]),
            wind_condition=WindCondition(
                1,
                14.84,
                area_density_code=2,
                basic_wind_speed_m_s=34,
            ),
            seismic_condition=SeismicCondition.ground(0.5),
        )

        result = calculator.calculate_one(pole, 9.69)

        self.assertEqual(result.fix_load_n, 900.7)
        self.assertEqual(result.wind_pressure_n_m2, 1683.4)
        self.assertEqual(result.wind_load_n, 1289.3)

    def test_decimal_taper_rounds_mass_to_one_decimal_before_gravity(self):
        pole = PoleObject(
            name="Taper",
            pole_type="Taper",
            diameter_lower_mm=300,
            diameter_upper_mm=200,
            thickness_lower_mm=6,
            thickness_upper_mm=4,
            material="STK400",
            top_elevation_m=10,
        )
        calculator = PoleCalculator(
            assembly=PoleAssembly([pole]),
            wind_condition=WindCondition(2, 10),
            seismic_condition=SeismicCondition.ground(0.5),
        )

        result = calculator.calculate_one(pole, 0)

        expected_mass = round(pole.raw_mass_kg(10, 300, 200), 1)
        self.assertEqual(result.mass_kg, expected_mass)
        self.assertEqual(
            result.fix_load_n,
            calculator.rounding.apply(
                expected_mass * 9.80665,
                CalculationValueType.LOAD,
            ),
        )

    def test_overdesign_factor_affects_fixload_and_seismic_load(self):
        base_result = self.calculator.calculate_one(self.pole, 0)
        amplified_calculator = PoleCalculator(
            assembly=PoleAssembly([self.pole]),
            wind_condition=WindCondition(2, 4),
            seismic_condition=SeismicCondition.ground(0.5),
            overdesign_factor=OverdesignFactor(1.2),
        )

        amplified_result = amplified_calculator.calculate_one(self.pole, 0)

        self.assertEqual(amplified_result.overdesign_factor, 1.2)
        self.assertEqual(
            amplified_result.fix_load_n,
            amplified_calculator.rounding.apply(
                self.pole.fix_load_n(
                    active_length_m=4,
                    diameter_at_active_bottom_mm=200,
                    diameter_at_active_top_mm=200,
                    overdesign_factor=OverdesignFactor(1.2),
                ),
                CalculationValueType.LOAD,
            ),
        )
        self.assertEqual(
            amplified_result.seismic_load_n,
            amplified_calculator.rounding.apply(
                amplified_result.fix_load_n * 0.5,
                CalculationValueType.LOAD,
            ),
        )

    def test_signed_xy_components_follow_vba(self):
        result = self.calculator.calculate_one(self.pole, 0)
        by_direction = {
            item.direction: item for item in result.directional_results
        }

        self.assertEqual(by_direction["E"].wind_load_x_n, -result.wind_load_n)
        self.assertEqual(by_direction["E"].wind_load_y_n, 0)
        self.assertEqual(by_direction["N"].wind_load_x_n, 0)
        self.assertEqual(by_direction["N"].wind_load_y_n, result.wind_load_n)
        self.assertEqual(
            by_direction["N"].wind_moment_x_nm,
            result.wind_moment_nm,
        )

    def test_quantity_other_than_one_is_rejected(self):
        with self.assertRaises(ValueError):
            PoleObject(
                name="P2",
                pole_type="Straight",
                diameter_lower_mm=200,
                diameter_upper_mm=200,
                thickness_lower_mm=5,
                thickness_upper_mm=5,
                material="STK400",
                top_elevation_m=4,
                quantity=2,
            )


class PoleAggregationTests(unittest.TestCase):
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
        self.calculator = PoleCalculator(
            assembly=PoleAssembly([self.upper, self.lower]),
            wind_condition=WindCondition(2, 10),
            seismic_condition=SeismicCondition.ground(0.5),
        )

    def test_scalar_totals_equal_sum_of_active_poles(self):
        aggregate = self.calculator.aggregate_at(0)
        results = aggregate.pole_results

        self.assertEqual(len(results), 2)
        self.assertAlmostEqual(
            aggregate.total_fix_load_n,
            sum(result.fix_load_n for result in results),
        )
        self.assertAlmostEqual(
            aggregate.total_seismic_load_n,
            sum(result.seismic_load_n for result in results),
        )
        self.assertAlmostEqual(
            aggregate.total_seismic_moment_nm,
            sum(result.seismic_moment_nm for result in results),
        )

    def test_directional_totals_equal_sum_of_active_poles(self):
        aggregate = self.calculator.aggregate_at(0)
        east = next(
            item
            for item in aggregate.directional_totals
            if item.direction == "E"
        )

        self.assertAlmostEqual(
            east.total_wind_load_n,
            sum(result.wind_load_n for result in aggregate.pole_results),
        )
        self.assertAlmostEqual(
            east.total_wind_load_x_n,
            sum(
                next(
                    item.wind_load_x_n
                    for item in result.directional_results
                    if item.direction == "E"
                )
                for result in aggregate.pole_results
            ),
        )
        self.assertAlmostEqual(
            east.total_wind_moment_y_nm,
            sum(
                next(
                    item.wind_moment_y_nm
                    for item in result.directional_results
                    if item.direction == "E"
                )
                for result in aggregate.pole_results
            ),
        )

    def test_direction_signs_are_preserved_after_aggregation(self):
        aggregate = self.calculator.aggregate_at(0)
        by_direction = {
            item.direction: item for item in aggregate.directional_totals
        }

        self.assertLess(by_direction["E"].total_wind_load_x_n, 0)
        self.assertGreater(by_direction["W"].total_wind_load_x_n, 0)
        self.assertGreater(by_direction["N"].total_wind_load_y_n, 0)
        self.assertLess(by_direction["S"].total_wind_load_y_n, 0)

    def test_only_poles_above_evaluated_position_are_aggregated(self):
        aggregate = self.calculator.aggregate_at(4)

        self.assertEqual(
            [result.geometry.pole_name for result in aggregate.pole_results],
            ["Upper"],
        )

    def test_no_active_pole_returns_zero_totals(self):
        aggregate = self.calculator.aggregate_at(10)

        self.assertEqual(aggregate.pole_results, ())
        self.assertEqual(aggregate.total_fix_load_n, 0.0)
        self.assertEqual(aggregate.total_seismic_load_n, 0.0)
        self.assertEqual(aggregate.total_seismic_moment_nm, 0.0)
        self.assertEqual(len(aggregate.directional_totals), 8)
        self.assertTrue(
            all(
                item.total_wind_load_n == 0.0
                for item in aggregate.directional_totals
            )
        )


if __name__ == "__main__":
    unittest.main()
