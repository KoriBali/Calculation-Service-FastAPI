"""Regression tests comparing Python helpers with M_Func_Basic.bas.

Ported from python_calc ``tests/test_basic_function.py`` (commit 270d23b).
"""

import unittest

from app.engine import basic_function as BasicFunction


class BasicFunctionTests(unittest.TestCase):
    def test_nnc_matches_confirmed_vba_formula(self):
        self.assertEqual(BasicFunction.nnC_P(0.8, 200), 0.786)

    def test_moment_of_inertia_uses_cm4_conversion(self):
        diameter = 200
        thickness = 5
        expected = round(
            (BasicFunction.PI / 64)
            * (diameter**4 - (diameter - 2 * thickness) ** 4)
            / 10000,
            2,
        )

        self.assertEqual(
            BasicFunction.Moment_Inertia(diameter, thickness),
            expected,
        )

    def test_straight_pole_mass_is_rounded_to_two_decimals(self):
        raw_mass = (
            BasicFunction.PI
            / 4
            * (200**2 - (200 - 2 * 5) ** 2)
            / 10**6
            * BasicFunction.DENSITY
            * 5
        )

        self.assertEqual(
            BasicFunction.Pole_WeightKg_Straight(200, 5, 5),
            round(raw_mass, 2),
        )

    def test_tapered_pole_mass_is_rounded_to_two_decimals(self):
        diameter_upper = 200
        diameter_lower = 300
        thickness_upper = 4
        thickness_lower = 6
        length = 10
        raw_mass = (
            BasicFunction.PI
            * length
            / 4
            * (
                ((diameter_lower - diameter_upper) / 2 + diameter_upper) ** 2
                - (
                    (
                        (diameter_lower - 2 * thickness_lower)
                        - (diameter_upper - 2 * thickness_upper)
                    )
                    / 2
                    + (diameter_upper - 2 * thickness_upper)
                )
                ** 2
            )
            / 10**6
            * BasicFunction.DENSITY
        )
        mass = BasicFunction.Pole_WeightKg_Taper(
            DiameterP_U=diameter_upper,
            DiameterP_L=diameter_lower,
            ThicknessP_U=thickness_upper,
            ThicknessP_L=thickness_lower,
            LengthP=length,
        )

        self.assertEqual(mass, round(raw_mass, 2))


if __name__ == "__main__":
    unittest.main()
