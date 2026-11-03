"""Tests for design-standard gravity selection.

Ported from python_calc ``tests/test_gravity.py`` (commit 270d23b).
"""

import unittest

from app.engine.calculation.gravity import gravity_for_standard


class GravityPolicyTests(unittest.TestCase):
    def test_non_new_jil_standards_use_standard_gravity(self):
        for standard in (1, 2, 3, 4, 5, 6, 9):
            with self.subTest(standard=standard):
                self.assertEqual(gravity_for_standard(standard), 9.80665)

    def test_new_jil_uses_vba_gravity(self):
        self.assertEqual(gravity_for_standard(7), 9.81)


if __name__ == "__main__":
    unittest.main()
