"""Tests for individual pole behaviour.

Ported from python_calc ``tests/test_pole.py`` (commit 270d23b).
"""

import unittest

from app.engine import basic_function as BasicFunction

from app.engine.domain.loads import OverdesignFactor
from app.engine.domain.pole import PoleObject


def straight_pole(name="P1", top=10.0, diameter=200.0):
    return PoleObject(
        name=name,
        pole_type="Straight",
        diameter_lower_mm=diameter,
        diameter_upper_mm=diameter,
        thickness_lower_mm=5.0,
        thickness_upper_mm=5.0,
        material="STK400",
        top_elevation_m=top,
    )


class PoleObjectTests(unittest.TestCase):
    def test_nnc_uses_confirmed_linear_interpolation(self):
        self.assertEqual(PoleObject.base_wind_coefficient(0.2, 200, 1), 0.7)
        self.assertEqual(PoleObject.base_wind_coefficient(0.8, 200, 1), 0.786)
        self.assertEqual(PoleObject.base_wind_coefficient(1.6, 200, 6), 0.9)

    def test_nnc_is_fixed_for_standards_two_through_five(self):
        for design_standard in (2, 3, 4, 5):
            with self.subTest(design_standard=design_standard):
                self.assertEqual(
                    PoleObject.base_wind_coefficient(
                        active_length_m=1.6,
                        diameter_mm=200,
                        design_standard=design_standard,
                    ),
                    0.7,
                )

    def test_straight_projected_area(self):
        pole = straight_pole()

        area = pole.projected_area(5.0, 200.0, 200.0)

        self.assertAlmostEqual(area, 1.0)

    def test_tapered_diameter_and_center(self):
        pole = PoleObject(
            name="TP1",
            pole_type="Taper",
            diameter_lower_mm=300,
            diameter_upper_mm=200,
            thickness_lower_mm=6,
            thickness_upper_mm=4,
            material="STK400",
            top_elevation_m=10,
        )

        diameter_mid = pole.diameter_at(5, 10)
        center = pole.local_load_center(10, 300, 200)

        self.assertAlmostEqual(diameter_mid, 250)
        self.assertAlmostEqual(center, 14 / 3)

    def test_straight_mass_uses_basic_function(self):
        pole = straight_pole()

        mass = pole.mass_kg(5.0, 200.0, 200.0)

        self.assertEqual(
            mass,
            BasicFunction.Pole_WeightKg_Straight(200, 5, 5),
        )

    def test_tapered_mass_uses_lower_and_upper_thickness(self):
        pole = PoleObject(
            name="TP1",
            pole_type="Taper",
            diameter_lower_mm=300,
            diameter_upper_mm=200,
            thickness_lower_mm=6,
            thickness_upper_mm=4,
            material="STK400",
            top_elevation_m=10,
        )

        mass = pole.mass_kg(10, 300, 200)

        self.assertEqual(
            mass,
            BasicFunction.Pole_WeightKg_Taper(200, 300, 4, 6, 10),
        )

    def test_fix_load_uses_mass_after_two_decimal_rounding(self):
        pole = straight_pole()
        mass = BasicFunction.Pole_WeightKg_Straight(200, 5, 5)

        fix_load = pole.fix_load_n(5, 200, 200)

        self.assertEqual(fix_load, mass * pole.GRAVITY)

    def test_fix_load_applies_overdesign_factor(self):
        pole = straight_pole()
        mass = pole.mass_kg(5, 200, 200)

        fix_load = pole.fix_load_n(
            5,
            200,
            200,
            OverdesignFactor(1.25),
        )

        self.assertEqual(fix_load, mass * pole.GRAVITY * 1.25)

    def test_seismic_load_is_fixload_times_k_value(self):
        pole = straight_pole()

        seismic_load = pole.calculate_seismic_load(
            fix_load_n=1000,
            k_value=0.5,
        )

        self.assertEqual(seismic_load, 500)

    def test_overdesign_factor_rejects_non_positive_value(self):
        with self.assertRaises(ValueError):
            OverdesignFactor(0)

    def test_section_properties_use_basic_functions(self):
        pole = straight_pole()

        properties = pole.section_properties(200)

        self.assertEqual(
            properties.cross_section_area_cm2,
            BasicFunction.Cross_AreaP(200, 5),
        )
        self.assertEqual(
            properties.section_modulus_cm3,
            BasicFunction.Section_Modulus(200, 5),
        )
        self.assertEqual(
            properties.moment_of_inertia_cm4,
            BasicFunction.Moment_Inertia(200, 5),
        )

    def test_wind_coefficient_uses_actual_active_bottom_diameter(self):
        pole = PoleObject(
            name="TP1",
            pole_type="Taper",
            diameter_lower_mm=300,
            diameter_upper_mm=200,
            thickness_lower_mm=6,
            thickness_upper_mm=4,
            material="STK400",
            top_elevation_m=10,
        )
        active_length = 1
        diameter_at_active_bottom = pole.diameter_at(
            distance_from_top_m=active_length,
            full_length_m=10,
        )

        cf = pole.wind_coefficient(
            active_length_m=active_length,
            diameter_at_active_bottom_mm=diameter_at_active_bottom,
            design_standard=2,
        )

        self.assertEqual(diameter_at_active_bottom, 210)
        self.assertEqual(cf, 0.7)


if __name__ == "__main__":
    unittest.main()
