"""Stage 9 tests for old lighting pole and small sign board workflows.

Ported from python_calc ``tests/test_standard_34_workflow.py`` (commit 270d23b).
"""

import unittest

from app.engine.calculation_service import CalculationService
from app.engine.calculation.pole_assembly import PoleAssembly
from app.engine.calculation.result import Standard34CalculationResult
from app.engine.calculation.standard_34_workflow import Standard34CalculationWorkflow
from app.engine.domain.loads import OverdesignFactor
from app.engine.domain.standards import DesignStandardFactory
from app.engine.domain.arm import Arm, ArmAssembly, ArmLoadObject, ArmPart
from tests.engine.regression_scenarios import (
    _direct_objects,
    _overhead_wires,
    _poles,
    create_calculator,
)


def workflow_for(code: int, *, include_oblique_wind: bool = False):
    standard = DesignStandardFactory.create(
        code,
        structure_height_m=8.15,
        include_oblique_wind=include_oblique_wind,
    )
    return Standard34CalculationWorkflow(
        design_standard=standard,
        pole_assembly=PoleAssembly(_poles()),
        direct_objects=_direct_objects(),
        overhead_wires=_overhead_wires(),
        overdesign_factor=OverdesignFactor(1.0),
    )


def arm_assembly():
    arm = Arm(
        name="Lighting arm",
        diameter_mm=114.3,
        thickness_mm=3.5,
        total_length_m=1.0,
        exposed_length_m=0.9,
        installation_height_m=5.0,
        material="STK400",
    )
    light = ArmLoadObject(
        name="Light",
        object_type="Directional",
        front_area_m2=0.266,
        side_area_m2=0.226,
        mass_per_unit_kg=20,
        horizontal_load_distance_m=0.9,
        base_wind_coefficient=1.0,
    )
    return ArmAssembly((ArmPart(arm, (light,)),))


class Standard34WorkflowTests(unittest.TestCase):
    def test_standard_three_adds_arm_to_load_moment_and_stress(self):
        standard = DesignStandardFactory.create(3, structure_height_m=8.15)
        without_arm = workflow_for(3).calculate_at(0.0)
        with_arm = Standard34CalculationWorkflow(
            design_standard=standard,
            pole_assembly=PoleAssembly(_poles()),
            direct_objects=_direct_objects(),
            overhead_wires=_overhead_wires(),
            arm_assembly=arm_assembly(),
        ).calculate_at(0.0)

        self.assertIsNotNone(with_arm.arm_aggregation)
        self.assertGreater(with_arm.total_fix_load_n, without_arm.total_fix_load_n)
        self.assertGreater(
            with_arm.direction_results[0].combined_wind_moment_nm,
            without_arm.direction_results[0].combined_wind_moment_nm,
        )
        self.assertGreater(
            with_arm.direction_results[0].bending_stress.bending_stress_n_mm2,
            without_arm.direction_results[0].bending_stress.bending_stress_n_mm2,
        )

    def test_standard_four_rejects_nonempty_arm_assembly(self):
        standard = DesignStandardFactory.create(4, structure_height_m=8.15)
        with self.assertRaisesRegex(ValueError, "does not use Arm"):
            Standard34CalculationWorkflow(
                design_standard=standard,
                pole_assembly=PoleAssembly(_poles()),
                arm_assembly=arm_assembly(),
            )

    def test_default_calculation_contains_straight_only(self):
        for code in (3, 4):
            with self.subTest(code=code):
                result = workflow_for(code).calculate_at(0.0)

                self.assertEqual(len(result.direction_results), 1)
                self.assertEqual(
                    result.direction_results[0].wind_case_name,
                    "STRAIGHT",
                )
                self.assertEqual(
                    result.direction_results[0].wind_direction_deg,
                    90.0,
                )

    def test_oblique_option_returns_separate_45_degree_result(self):
        for code in (3, 4):
            with self.subTest(code=code):
                result = workflow_for(
                    code,
                    include_oblique_wind=True,
                ).calculate_at(0.0)

                self.assertEqual(
                    tuple(item.wind_case_name for item in result.direction_results),
                    ("STRAIGHT", "OBLIQUE"),
                )
                self.assertEqual(
                    tuple(item.wind_direction_deg for item in result.direction_results),
                    (90.0, 45.0),
                )

    def test_straight_and_oblique_match_legacy_n_and_ne(self):
        for code in (3, 4):
            with self.subTest(code=code):
                new = workflow_for(
                    code,
                    include_oblique_wind=True,
                ).calculate_at(0.0)
                old = create_calculator(code).calculate_at(0.0)
                legacy_by_direction = {
                    item.direction: item for item in old.directional_results
                }

                for new_name, old_name in (("STRAIGHT", "N"), ("OBLIQUE", "NE")):
                    new_result = next(
                        item
                        for item in new.direction_results
                        if item.wind_case_name == new_name
                    )
                    old_result = legacy_by_direction[old_name]
                    for field in (
                        "total_wind_load_n",
                        "resultant_wind_load_n",
                        "combined_wind_moment_nm",
                    ):
                        self.assertEqual(
                            getattr(new_result, field),
                            getattr(old_result, field),
                        )
                    self.assertEqual(
                        new_result.bending_stress.bending_stress_n_mm2,
                        old_result.wind_strength.calculated_stress_n_mm2,
                    )
                    self.assertEqual(
                        new_result.bending_stress.safety_factor,
                        old_result.wind_strength.utilization_ratio,
                    )

    def test_seismic_is_disabled_for_every_object(self):
        for code in (3, 4):
            with self.subTest(code=code):
                result = workflow_for(code).calculate_at(0.0)

                self.assertEqual(result.pole_aggregation.total_seismic_load_n, 0.0)
                self.assertEqual(
                    result.direct_object_aggregation.total_seismic_load_n,
                    0.0,
                )
                self.assertEqual(
                    result.overhead_wire_aggregation.total_seismic_load_n,
                    0.0,
                )
                self.assertEqual(
                    result.overhead_wire_aggregation.total_seismic_tension_n,
                    0.0,
                )

    def test_public_result_has_no_compression_torque_or_seismic_fields(self):
        top_fields = set(Standard34CalculationResult.__dataclass_fields__)
        result = workflow_for(3).calculate_at(0.0)
        direction_fields = set(
            type(result.direction_results[0]).__dataclass_fields__
        )

        for field_name in top_fields | direction_fields:
            normalized = field_name.lower()
            self.assertNotIn("compression", normalized)
            self.assertNotIn("torque", normalized)
            self.assertNotIn("torsion", normalized)
            self.assertNotIn("seismic", normalized)

    def test_bending_stress_uses_short_term_allowable_and_status(self):
        result = workflow_for(3).calculate_at(0.0)
        bending = result.direction_results[0].bending_stress

        self.assertEqual(bending.short_term_allowable_bending_n_mm2, 235.0)
        self.assertIn(bending.status, {"O.K", "N.G"})
        self.assertEqual(
            bending.status,
            "O.K" if bending.safety_factor <= 1.0 else "N.G",
        )

    def test_optional_special_seismic_is_explicitly_unavailable(self):
        standard = DesignStandardFactory.create(
            3,
            structure_height_m=8.15,
            enable_optional_seismic=True,
            k_value=0.5,
        )

        with self.assertRaisesRegex(
            NotImplementedError,
            "Optional special seismic",
        ):
            Standard34CalculationWorkflow(
                design_standard=standard,
                pole_assembly=PoleAssembly(_poles()),
            )

    def test_result_is_stage_specific(self):
        result = workflow_for(4).calculate_at(0.0)

        self.assertIsInstance(result, Standard34CalculationResult)

    def test_application_service_calls_standard_34_workflow(self):
        service = CalculationService(
            workflow_for(3, include_oblique_wind=True)
        )

        result = service.calculate((0.0,))[0]

        self.assertEqual(
            tuple(item.wind_case_name for item in result.direction_results),
            ("STRAIGHT", "OBLIQUE"),
        )


if __name__ == "__main__":
    unittest.main()
