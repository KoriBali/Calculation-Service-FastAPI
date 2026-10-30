"""Tests for OHW load, tension, moment, and aggregation.

Ported from python_calc ``tests/test_overhead_wire.py`` (commit 270d23b).
"""

import unittest
from math import cos, radians

from app.engine.calculation.overhead_wire_calculator import OverheadWireCalculator
from app.engine.calculation.rounding import CalculationValueType
from app.engine.domain.conditions import SeismicCondition, WindCondition
from app.engine.domain.overhead_wire import OverheadWire


def make_wire(name="W1", elevation=10, fixed_angle=0, vertical_angle=0):
    return OverheadWire(
        name=name,
        mass_per_length_kg_m=2,
        diameter_mm=20,
        elevation_m=elevation,
        span_length_m=40,
        sag_ratio_percent=2,
        base_wind_coefficient=1.1,
        fixed_angle_deg=fixed_angle,
        vertical_angle_deg=vertical_angle,
    )


class OverheadWireTests(unittest.TestCase):
    def test_span_is_metres_and_support_uses_half_span(self):
        wire = make_wire(vertical_angle=30)

        self.assertEqual(wire.tributary_horizontal_length_m(), 20)
        self.assertAlmostEqual(
            wire.tributary_wire_length_m(),
            20 / cos(radians(30)),
        )

    def test_fixload_has_no_overdesign_factor(self):
        wire = make_wire()

        self.assertEqual(wire.total_mass_kg(), 40)
        self.assertEqual(wire.fix_load_n(), 40 * wire.GRAVITY)

    def test_projected_area_uses_vertical_and_attack_angles(self):
        wire = make_wire(fixed_angle=0, vertical_angle=30)
        base_area = 0.02 * 20 / cos(radians(30))

        self.assertAlmostEqual(wire.projected_area(), base_area)
        self.assertEqual(wire.projected_area(0), 0)

    def test_wind_tension_components_use_fixed_angle_in_radians(self):
        wire = make_wire(fixed_angle=90)
        tension_x, tension_y = wire.wind_tension_components_n(100)

        self.assertEqual(tension_x, 0)
        self.assertEqual(tension_y, -100)

    def test_seismic_tension_does_not_use_k_value(self):
        wire = make_wire()
        expected = wire.tension_from_line_load(
            wire.fix_load_per_length_n_m()
        )

        self.assertEqual(wire.seismic_tension_n(), expected)


class OverheadWireCalculatorTests(unittest.TestCase):
    def setUp(self):
        self.lower = make_wire("Lower", elevation=5, fixed_angle=0)
        self.upper = make_wire("Upper", elevation=10, fixed_angle=45)
        self.calculator = OverheadWireCalculator(
            wires=[self.lower, self.upper],
            wind_condition=WindCondition(2, 10),
            seismic_condition=SeismicCondition.ground(0.5),
        )

    def test_wire_at_evaluated_position_remains_active(self):
        aggregate = self.calculator.aggregate_at(5)
        lower = next(
            result
            for result in aggregate.wire_results
            if result.wire_name == "Lower"
        )

        self.assertEqual(aggregate.active_wire_count, 2)
        self.assertEqual(lower.load_center_height_m, 0)
        self.assertGreater(lower.fix_load_n, 0)
        self.assertGreater(lower.seismic_load_n, 0)
        self.assertEqual(lower.seismic_moment_nm, 0)

    def test_seismic_load_uses_fixload_times_k_value(self):
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

    def test_seismic_tension_moment_varies_with_angle_of_attack(self):
        result = self.calculator.calculate_one(self.upper, 4)
        by_direction = {
            item.direction: item for item in result.directional_results
        }

        self.assertNotEqual(
            by_direction["E"].seismic_tension_moment_nm,
            by_direction["S"].seismic_tension_moment_nm,
        )

    def test_aggregation_sums_loads_tensions_and_moments(self):
        aggregate = self.calculator.aggregate_at(0)
        north = next(
            item
            for item in aggregate.directional_totals
            if item.direction == "N"
        )

        self.assertAlmostEqual(
            aggregate.total_fix_load_n,
            sum(result.fix_load_n for result in aggregate.wire_results),
        )
        self.assertAlmostEqual(
            aggregate.total_seismic_tension_n,
            sum(
                result.seismic_tension_n
                for result in aggregate.wire_results
            ),
        )
        self.assertAlmostEqual(
            north.total_wind_tension_n,
            sum(
                next(
                    item.wind_tension_n
                    for item in result.directional_results
                    if item.direction == "N"
                )
                for result in aggregate.wire_results
            ),
        )


if __name__ == "__main__":
    unittest.main()
