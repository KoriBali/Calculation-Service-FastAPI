"""Tests for assembled pole geometry at evaluated positions.

Ported from python_calc ``tests/test_pole_assembly.py`` (commit 270d23b).
"""

import unittest

from app.engine.calculation.pole_assembly import PoleAssembly
from app.engine.domain.pole import PoleObject


def pole(name, top, diameter):
    return PoleObject(
        name=name,
        pole_type="Straight",
        diameter_lower_mm=diameter,
        diameter_upper_mm=diameter,
        thickness_lower_mm=5,
        thickness_upper_mm=5,
        material="STK400",
        top_elevation_m=top,
    )


class PoleAssemblyTests(unittest.TestCase):
    def setUp(self):
        self.lower = pole("Lower", 4.0, 220)
        self.middle = pole("Middle", 9.0, 190)
        self.upper = pole("Upper", 14.0, 165)
        self.assembly = PoleAssembly(
            [self.upper, self.lower, self.middle]
        )

    def test_segments_are_ordered_bottom_up(self):
        self.assertEqual(
            [item.name for item in self.assembly.poles],
            ["Lower", "Middle", "Upper"],
        )

    def test_partial_segment_at_evaluated_position(self):
        geometry = self.assembly.active_geometry(self.middle, 6.0)

        self.assertEqual(geometry.segment_bottom_m, 4.0)
        self.assertEqual(geometry.segment_top_m, 9.0)
        self.assertEqual(geometry.active_bottom_m, 6.0)
        self.assertEqual(geometry.active_length_m, 3.0)
        self.assertEqual(geometry.load_center_height_m, 1.5)

    def test_upper_segment_load_center_height_includes_offset(self):
        geometry = self.assembly.active_geometry(self.upper, 6.0)

        self.assertEqual(geometry.active_length_m, 5.0)
        self.assertEqual(geometry.load_center_height_m, 5.5)

    def test_only_poles_above_position_are_active(self):
        active = self.assembly.active_poles(9.0)

        self.assertEqual([item.name for item in active], ["Upper"])

    def test_inactive_geometry_does_not_have_reversed_bounds(self):
        geometry = self.assembly.active_geometry(self.lower, 10.0)

        self.assertEqual(geometry.active_bottom_m, 4.0)
        self.assertEqual(geometry.active_top_m, 4.0)
        self.assertEqual(geometry.active_length_m, 0.0)
        self.assertEqual(geometry.load_center_height_m, 0.0)


if __name__ == "__main__":
    unittest.main()
