"""Tests for stable DesignStandard identities.

Ported from python_calc ``tests/test_design_standard_codes.py`` (commit 270d23b).
"""

import json
import unittest

from app.engine.domain.standards import DesignStandardCode


class DesignStandardCodeTests(unittest.TestCase):
    def test_codes_one_through_nine_are_recognized(self):
        expected_members = (
            DesignStandardCode.ACT_DISASTER_PREVENTION,
            DesignStandardCode.FIXED_WIND_DISASTER,
            DesignStandardCode.OLD_LIGHTING_POLE,
            DesignStandardCode.SMALL_SIGN_BOARD,
            DesignStandardCode.LARGE_SIGN_BOARD,
            DesignStandardCode.ACT_TOWER,
            DesignStandardCode.NEW_JIL,
            DesignStandardCode.HAIDEN_KITEI,
            DesignStandardCode.OLD_TRAFFIC_SIGNAL,
        )

        self.assertEqual(
            tuple(DesignStandardCode(code) for code in range(1, 10)),
            expected_members,
        )

    def test_invalid_codes_are_rejected(self):
        for invalid_code in (0, 10, -1, 99, "NEW_JIL"):
            with self.subTest(invalid_code=invalid_code):
                with self.assertRaises(ValueError):
                    DesignStandardCode(invalid_code)

    def test_enum_remains_integer_compatible(self):
        standard = DesignStandardCode.NEW_JIL

        self.assertEqual(standard, 7)
        self.assertEqual(int(standard), 7)

    def test_enum_serializes_as_integer_in_json(self):
        serialized = json.dumps(
            {"design_standard": DesignStandardCode.NEW_JIL}
        )

        self.assertEqual(serialized, '{"design_standard": 7}')

    def test_haiden_kitei_is_identified_but_calculation_is_unavailable(self):
        standard = DesignStandardCode(8)

        self.assertIs(standard, DesignStandardCode.HAIDEN_KITEI)
        self.assertFalse(standard.calculation_is_available)
        with self.assertRaisesRegex(
            NotImplementedError,
            r"Haiden Kitei.*d_st = 8",
        ):
            standard.ensure_calculation_is_available()

    def test_other_identified_standards_pass_availability_guard(self):
        for standard in DesignStandardCode:
            if standard is DesignStandardCode.HAIDEN_KITEI:
                continue
            with self.subTest(standard=standard):
                self.assertTrue(standard.calculation_is_available)
                self.assertIsNone(
                    standard.ensure_calculation_is_available()
                )


if __name__ == "__main__":
    unittest.main()
