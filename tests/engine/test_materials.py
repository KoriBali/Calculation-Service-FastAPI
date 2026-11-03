"""Tests for pole material domain objects.

Ported from python_calc ``tests/test_materials.py`` (commit 270d23b).
"""

import unittest

from app.engine.domain.materials import get_pole_material


class PoleMaterialTests(unittest.TestCase):
    def test_material_lookup_is_case_insensitive(self):
        material = get_pole_material("stk400")

        self.assertEqual(material.name, "STK400")
        self.assertEqual(material.short_term_allowable_bending, 235)

    def test_missing_optional_property_is_reported(self):
        material = get_pole_material("SGP")

        with self.assertRaises(ValueError):
            material.require_shear()


if __name__ == "__main__":
    unittest.main()
