"""Tests for Direct Object behaviour and aggregation.

Ported from python_calc ``tests/test_direct_object.py`` (commit 270d23b).
"""

import unittest

from app.engine.calculation.direct_object_calculator import DirectObjectCalculator
from app.engine.calculation.rounding import CalculationValueType
from app.engine.domain.conditions import SeismicCondition, WindCondition
from app.engine.domain.direct_object import DirectObject


def directional_object(name="Panel", elevation=10, quantity=2):
    return DirectObject(
        name=name,
        object_type="Directional",
        front_area_m2=2,
        side_area_m2=1,
        mass_per_unit_kg=100,
        elevation_m=elevation,
        base_wind_coefficient=1.2,
        quantity=quantity,
        fixed_angle_deg=0,
    )


class DirectObjectTests(unittest.TestCase):
    def test_fixload_does_not_use_pole_overdesign_factor(self):
        direct_object = directional_object()

        self.assertEqual(
            direct_object.fix_load_n(),
            100 * 2 * direct_object.GRAVITY,
        )

    def test_directional_area_uses_front_and_side_projection(self):
        direct_object = directional_object()

        self.assertEqual(direct_object.projected_area(0), 2)
        self.assertEqual(direct_object.projected_area(3.14159265358979 / 2), 4)

    def test_omni_ignores_side_area(self):
        direct_object = DirectObject(
            name="Antenna",
            object_type="Omni",
            front_area_m2=2,
            side_area_m2=999,
            mass_per_unit_kg=20,
            elevation_m=8,
            base_wind_coefficient=1.0,
            quantity=3,
            fixed_angle_deg=35,
        )

        self.assertEqual(direct_object.projected_area(0), 6)
        self.assertEqual(direct_object.projected_area(1.7), 6)

    def test_standard_one_applies_kz_to_cf(self):
        direct_object = directional_object()

        self.assertEqual(direct_object.wind_coefficient(1, 0.8), 0.96)
        self.assertEqual(direct_object.wind_coefficient(6, 0.8), 1.2)


class DirectObjectCalculatorTests(unittest.TestCase):
    def setUp(self):
        self.lower = directional_object("Lower", elevation=5, quantity=1)
        self.upper = directional_object("Upper", elevation=10, quantity=2)
        self.calculator = DirectObjectCalculator(
            direct_objects=[self.lower, self.upper],
            wind_condition=WindCondition(2, 10),
            seismic_condition=SeismicCondition.ground(0.5),
        )

    def test_object_at_evaluated_position_remains_active(self):
        aggregate = self.calculator.aggregate_at(5)
        by_name = {
            result.object_name: result
            for result in aggregate.direct_object_results
        }

        self.assertEqual(aggregate.active_object_count, 2)
        self.assertEqual(by_name["Lower"].load_center_height_m, 0)
        self.assertGreater(by_name["Lower"].fix_load_n, 0)
        self.assertGreater(by_name["Lower"].seismic_load_n, 0)
        self.assertEqual(by_name["Lower"].seismic_moment_nm, 0)

    def test_object_below_evaluated_position_is_excluded(self):
        aggregate = self.calculator.aggregate_at(6)

        self.assertEqual(aggregate.active_object_count, 1)
        self.assertEqual(
            aggregate.direct_object_results[0].object_name,
            "Upper",
        )

    def test_seismic_load_and_moment_follow_confirmed_rule(self):
        result = self.calculator.calculate_one(self.upper, 4)

        self.assertEqual(
            result.seismic_load_n,
            self.calculator.rounding.apply(
                result.fix_load_n * 0.5,
                CalculationValueType.LOAD,
            ),
        )
        self.assertEqual(
            result.seismic_moment_nm,
            self.calculator.rounding.apply(
                result.seismic_load_n * 6,
                CalculationValueType.MOMENT,
            ),
        )

    def test_directional_components_and_moments_follow_vba(self):
        result = self.calculator.calculate_one(self.upper, 4)
        by_direction = {
            item.direction: item for item in result.directional_results
        }

        self.assertLess(by_direction["E"].wind_load_x_n, 0)
        self.assertEqual(by_direction["E"].wind_load_y_n, 0)
        self.assertGreater(by_direction["N"].wind_load_y_n, 0)
        self.assertEqual(
            by_direction["N"].wind_moment_x_nm,
            self.calculator.rounding.apply(
                by_direction["N"].wind_load_y_n * 6,
                CalculationValueType.MOMENT,
            ),
        )

    def test_aggregation_sums_active_objects_per_direction(self):
        aggregate = self.calculator.aggregate_at(0)
        north = next(
            item
            for item in aggregate.directional_totals
            if item.direction == "N"
        )

        self.assertAlmostEqual(
            aggregate.total_fix_load_n,
            sum(
                result.fix_load_n
                for result in aggregate.direct_object_results
            ),
        )
        self.assertAlmostEqual(
            aggregate.total_seismic_load_n,
            sum(
                result.seismic_load_n
                for result in aggregate.direct_object_results
            ),
        )
        self.assertAlmostEqual(
            north.total_wind_load_n,
            sum(
                next(
                    item.wind_load_n
                    for item in result.directional_results
                    if item.direction == "N"
                )
                for result in aggregate.direct_object_results
            ),
        )


if __name__ == "__main__":
    unittest.main()
