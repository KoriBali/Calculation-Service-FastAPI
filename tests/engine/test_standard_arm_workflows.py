"""Integration tests for Arm-enabled standards 5, 7 and 9.

Ported from python_calc ``tests/test_standard_arm_workflows.py`` (commit 270d23b).
"""

import unittest

from app.engine.calculation_service import CalculationService
from app.engine.calculation.pole_assembly import PoleAssembly
from app.engine.calculation.standard_arm_workflows import (
    Standard5CalculationWorkflow,
    Standard7CalculationWorkflow,
    Standard9CalculationWorkflow,
)
from app.engine.domain.arm import Arm, ArmAssembly, ArmLoadObject, ArmPart
from app.engine.domain.direct_object import DirectObject
from app.engine.domain.overhead_wire import OverheadWire
from app.engine.domain.pole import PoleObject
from app.engine.domain.standards import DesignStandardFactory


def pole_assembly():
    return PoleAssembly(
        (
            PoleObject(
                name="Main pole",
                pole_type="Straight",
                diameter_lower_mm=216.3,
                diameter_upper_mm=216.3,
                thickness_lower_mm=5.8,
                thickness_upper_mm=5.8,
                material="STK400",
                top_elevation_m=8.0,
            ),
        )
    )


def arm_assembly():
    arm = Arm(
        name="Signal arm",
        diameter_mm=114.3,
        thickness_mm=3.5,
        total_length_m=1.5,
        exposed_length_m=1.4,
        installation_height_m=6.0,
        material="STK400",
        fixed_angle_deg=20,
    )
    signal = ArmLoadObject(
        name="Signal",
        object_type="Directional",
        front_area_m2=0.266,
        side_area_m2=0.226,
        mass_per_unit_kg=20,
        horizontal_load_distance_m=1.2,
        base_wind_coefficient=1.0,
    )
    return ArmAssembly((ArmPart(arm, (signal,)),))


def direct_objects():
    return (
        DirectObject(
            name="Box",
            object_type="Directional",
            front_area_m2=0.2,
            side_area_m2=0.1,
            mass_per_unit_kg=10,
            elevation_m=5,
            base_wind_coefficient=1.2,
            quantity=1,
            fixed_angle_deg=15,
        ),
    )


def wires():
    return (
        OverheadWire(
            name="Wire",
            mass_per_length_kg_m=0.19,
            diameter_mm=11.5,
            elevation_m=5.5,
            span_length_m=10,
            sag_ratio_percent=3,
            base_wind_coefficient=1.0,
            fixed_angle_deg=180,
            vertical_angle_deg=0,
        ),
    )


def workflow(code):
    standard = DesignStandardFactory.create(code, structure_height_m=8)
    workflow_type = {
        5: Standard5CalculationWorkflow,
        7: Standard7CalculationWorkflow,
        9: Standard9CalculationWorkflow,
    }[code]
    return workflow_type(
        design_standard=standard,
        pole_assembly=pole_assembly(),
        direct_objects=direct_objects(),
        overhead_wires=wires(),
        arm_assembly=arm_assembly(),
    )


class Standard5WorkflowTests(unittest.TestCase):
    def test_integrates_arm_into_straight_oblique_and_pole_stress(self):
        result = workflow(5).calculate_at(0)
        self.assertEqual(
            tuple(item.wind_case_name for item in result.direction_results),
            ("STRAIGHT", "OBLIQUE"),
        )
        self.assertEqual(result.arm_aggregation.active_arm_count, 1)
        self.assertGreater(result.total_fix_load_n, result.pole_aggregation.total_fix_load_n)
        self.assertNotEqual(result.direction_results[1].wind_torsional_moment_nm, 0)
        self.assertEqual(
            result.stress_result.straight.absolute_total_bending_moment_nm,
            result.direction_results[0].combined_wind_moment_nm,
        )
        self.assertEqual(result.arm_aggregation.total_seismic_load_n, 0)

    def test_requires_active_arm_for_buckling_reference(self):
        with self.assertRaisesRegex(ValueError, "requires an active Arm"):
            workflow(5).calculate_at(7)


class Standard7WorkflowTests(unittest.TestCase):
    def test_integrates_complete_eight_direction_arm_response(self):
        result = workflow(7).calculate_at(0)
        self.assertEqual(len(result.direction_results), 8)
        self.assertEqual(len(result.stress_result.direction_results), 8)
        self.assertGreater(result.arm_aggregation.total_seismic_load_n, 0)
        self.assertGreater(result.total_seismic_load_n, 0)
        self.assertTrue(
            any(item.wind_torsional_moment_nm != 0 for item in result.direction_results)
        )
        self.assertTrue(
            any(
                item.seismic_torsional_moment_nm != 0
                for item in result.direction_results
            )
        )
        self.assertEqual(
            result.stress_result.direction_results[0].absolute_combined_wind_moment_nm,
            abs(result.direction_results[0].combined_wind_moment_nm),
        )


class Standard9WorkflowTests(unittest.TestCase):
    def test_integrates_eight_directions_without_seismic(self):
        result = workflow(9).calculate_at(0)
        self.assertEqual(len(result.direction_results), 8)
        self.assertEqual(len(result.stress_result.direction_results), 8)
        self.assertEqual(result.arm_aggregation.total_seismic_load_n, 0)
        self.assertTrue(
            all(
                item.seismic_torsional_moment_nm == 0
                for item in result.direction_results
            )
        )
        self.assertEqual(
            result.stress_result.direction_results[0].absolute_total_bending_moment_nm,
            abs(result.direction_results[0].combined_wind_moment_nm),
        )

    def test_application_service_accepts_all_arm_workflows(self):
        for code in (5, 7, 9):
            with self.subTest(code=code):
                result = CalculationService(workflow(code)).calculate((0,))[0]
                self.assertEqual(int(result.design_standard.code), code)


if __name__ == "__main__":
    unittest.main()
