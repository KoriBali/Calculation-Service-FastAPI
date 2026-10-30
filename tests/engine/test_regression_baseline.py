"""Controlled regression values after calculation-rounding integration.

The original pre-refactor values remain documented in
``docs/stage_0_regression_baseline.md``. These assertions intentionally lock
the confirmed rule that every new calculation is rounded before its result is
used by the next calculation.
"""

import unittest

from tests.engine.regression_scenarios import scenario_snapshot


EXPECTED_BASELINE = {
    1: {
        "area_density_code": 2,
        "wind_pressures": (4443.1, 4443.1, 4443.1),
        "positions": (
            (6.65, "Pole-1", 172.0, 86.1, 669.6, 665.5, 40.1, "O.K"),
            (1.65, "Pole-2", 814.6, 407.4, 3275.6, 15714.2,
             176.9, "O.K"),
            (0.0, "Pole-3", 1103.2, 551.7, 4219.3, 23413.3,
             263.5, "N.G"),
        ),
    },
    2: {
        "area_density_code": None,
        "wind_pressures": (2214.0, 2214.0, 2214.0),
        "positions": (
            (6.65, "Pole-1", 172.0, 86.1, 283.6, 294.1, 17.7, "O.K"),
            (1.65, "Pole-2", 814.6, 407.4, 1405.4, 7957.1,
             89.6, "O.K"),
            (0.0, "Pole-3", 1103.2, 551.7, 1828.5, 11661.1,
             131.2, "O.K"),
        ),
    },
    3: {
        "area_density_code": None,
        "wind_pressures": (2214.0, 2214.0, 2214.0),
        "positions": (
            (6.65, "Pole-1", 172.0, 0.0, 283.6, 294.1, 17.7, "O.K"),
            (1.65, "Pole-2", 814.6, 0.0, 1405.4, 7957.1,
             89.6, "O.K"),
            (0.0, "Pole-3", 1103.2, 0.0, 1828.5, 11661.1,
             131.2, "O.K"),
        ),
    },
    6: {
        "area_density_code": 2,
        "wind_pressures": (6309.2, 5937.0, 5451.2),
        "positions": (
            (6.65, "Pole-1", 172.0, 86.1, 950.8, 945.0, 57.0, "O.K"),
            (1.65, "Pole-2", 814.6, 407.4, 4651.0, 22309.9,
             251.1, "N.G"),
            (0.0, "Pole-3", 1103.2, 551.7, 5990.4, 33240.3,
             374.1, "N.G"),
        ),
    },
}


class CalculationRoundingRegressionTests(unittest.TestCase):
    def test_existing_calculation_values_through_evaluated_position(self):
        for design_standard, expected in EXPECTED_BASELINE.items():
            with self.subTest(design_standard=design_standard):
                snapshot = scenario_snapshot(design_standard)
                self.assertEqual(
                    snapshot["area_density_code"],
                    expected["area_density_code"],
                )

                actual_pressures = tuple(
                    snapshot["wind_pressure_by_pole_top_n_m2"][str(top)]
                    for top in (8.15, 6.65, 1.65)
                )
                self._assert_float_sequence(
                    actual_pressures,
                    expected["wind_pressures"],
                )

                for actual, expected_position in zip(
                    snapshot["evaluated_positions"],
                    expected["positions"],
                    strict=True,
                ):
                    north = actual["north_report_result"]
                    wind_strength = north["wind_strength"]
                    actual_position = (
                        actual["evaluated_position_m"],
                        actual["evaluated_pole_name"],
                        actual["total_fix_load_n"],
                        actual["total_seismic_load_n"],
                        north["total_wind_load_n"],
                        north["combined_wind_moment_nm"],
                        wind_strength["calculated_stress_n_mm2"],
                        wind_strength["status"],
                    )
                    self._assert_mixed_sequence(
                        actual_position,
                        expected_position,
                    )

    def test_area_density_code_reference_for_standards_one_and_six(self):
        for design_standard in (1, 6):
            with self.subTest(design_standard=design_standard):
                snapshot = scenario_snapshot(design_standard)
                common = snapshot["common_parameters"]
                self.assertEqual(common["area_density_code"], 2)
                self.assertEqual(common["area_density_code_symbol"], "II")
                self.assertEqual(common["alpha"], 0.15)
                self.assertEqual(common["zb"], 5.0)
                self.assertEqual(common["zg"], 350.0)

    def _assert_float_sequence(self, actual, expected):
        self.assertEqual(len(actual), len(expected))
        for actual_value, expected_value in zip(actual, expected, strict=True):
            self.assertAlmostEqual(actual_value, expected_value, places=9)

    def _assert_mixed_sequence(self, actual, expected):
        self.assertEqual(len(actual), len(expected))
        for actual_value, expected_value in zip(actual, expected, strict=True):
            if isinstance(expected_value, float):
                self.assertAlmostEqual(actual_value, expected_value, places=9)
            else:
                self.assertEqual(actual_value, expected_value)


if __name__ == "__main__":
    unittest.main()
