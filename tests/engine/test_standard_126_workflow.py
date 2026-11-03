"""Stage 8 parity and integration tests for d_st 1, 2, and 6.

Ported from python_calc ``tests/test_standard_126_workflow.py`` (commit 270d23b).
"""

import unittest

from app.engine.calculation_service import CalculationService
from app.engine.calculation.direct_object_calculator import DirectObjectCalculator
from app.engine.calculation.evaluated_position_calculator import EvaluatedPositionCalculator
from app.engine.calculation.overhead_wire_calculator import OverheadWireCalculator
from app.engine.calculation.pole_assembly import PoleAssembly
from app.engine.calculation.pole_calculator import PoleCalculator
from app.engine.calculation.seismic import NoSeismicPolicy
from app.engine.calculation.standard_126_workflow import Standard126CalculationWorkflow
from app.engine.domain.conditions import SeismicCondition
from app.engine.domain.loads import OverdesignFactor
from app.engine.domain.standards import DesignStandardFactory
from tests.engine.regression_scenarios import (
    _direct_objects,
    _overhead_wires,
    _poles,
    wind_condition_for,
)


def standard_for(code: int):
    arguments = {
        "structure_height_m": 8.15,
        "k_value": 0.5,
    }
    if code in {1, 6}:
        arguments.update(
            area_density_code=2,
            basic_wind_speed_m_s=60.0,
        )
    return DesignStandardFactory.create(code, **arguments)


def new_workflow(code: int) -> Standard126CalculationWorkflow:
    return Standard126CalculationWorkflow(
        design_standard=standard_for(code),
        pole_assembly=PoleAssembly(_poles()),
        seismic_condition=SeismicCondition.ground(0.5),
        direct_objects=_direct_objects(),
        overhead_wires=_overhead_wires(),
        overdesign_factor=OverdesignFactor(1.0),
    )


def comparable_legacy_calculator(code: int) -> EvaluatedPositionCalculator:
    wind = wind_condition_for(code)
    seismic = SeismicCondition.ground(0.5)
    pole = PoleCalculator(
        PoleAssembly(_poles()),
        wind,
        seismic,
        OverdesignFactor(1.0),
    )
    direct = DirectObjectCalculator(_direct_objects(), wind, seismic)
    wire = OverheadWireCalculator(
        _overhead_wires(),
        wind,
        seismic,
        seismic_policy=NoSeismicPolicy(),
        calculate_seismic_tension=False,
    )
    return EvaluatedPositionCalculator(pole, direct, wire)


class Standard126WorkflowTests(unittest.TestCase):
    def test_new_workflow_has_only_one_omni_direction_everywhere(self):
        for code in (1, 2, 6):
            with self.subTest(code=code):
                result = new_workflow(code).calculate_at(0.0)
                directional_groups = (
                    result.pole_aggregation.directional_totals,
                    result.direct_object_aggregation.directional_totals,
                    result.overhead_wire_aggregation.directional_totals,
                    result.evaluated_position_result.directional_results,
                )
                for group in directional_groups:
                    self.assertEqual(len(group), 1)
                    self.assertEqual(group[0].direction, "OMNI")

    def test_object_intermediates_match_legacy_north_case(self):
        for code in (1, 2, 6):
            with self.subTest(code=code):
                workflow = new_workflow(code)
                new = workflow.calculate_at(0.0)
                legacy_calculator = comparable_legacy_calculator(code)
                old = legacy_calculator.calculate_at(0.0)

                new_pole = new.pole_aggregation.pole_results[0]
                old_pole = legacy_calculator.pole_calculator.calculate_at(0.0)[0]
                for field in (
                    "mass_kg",
                    "fix_load_n",
                    "projected_area_m2",
                    "cf",
                    "wind_pressure_n_m2",
                    "wind_load_n",
                    "seismic_load_n",
                    "wind_moment_nm",
                    "seismic_moment_nm",
                ):
                    self.assertEqual(getattr(new_pole, field), getattr(old_pole, field))
                self.assertEqual(
                    new_pole.geometry.load_center_height_m,
                    old_pole.geometry.load_center_height_m,
                )

                new_direct = new.direct_object_aggregation.direct_object_results[0]
                old_direct = (
                    legacy_calculator.direct_object_calculator.calculate_at(0.0)[0]
                )
                for field in (
                    "total_mass_kg",
                    "fix_load_n",
                    "cf",
                    "wind_pressure_n_m2",
                    "seismic_load_n",
                    "seismic_moment_nm",
                    "load_center_height_m",
                ):
                    self.assertEqual(
                        getattr(new_direct, field), getattr(old_direct, field)
                    )
                self.assertEqual(
                    new_direct.directional_results[0].projected_area_m2,
                    old_direct.directional_results[0].projected_area_m2,
                )
                self.assertEqual(
                    new_direct.directional_results[0].wind_load_n,
                    old_direct.directional_results[0].wind_load_n,
                )

                new_wire = new.overhead_wire_aggregation.wire_results[0]
                old_wire = (
                    legacy_calculator.overhead_wire_calculator.calculate_at(0.0)[0]
                )
                for field in (
                    "total_mass_kg",
                    "fix_load_n",
                    "projected_area_m2",
                    "cf",
                    "wind_pressure_n_m2",
                    "load_center_height_m",
                ):
                    self.assertEqual(getattr(new_wire, field), getattr(old_wire, field))
                self.assertEqual(new_wire.seismic_load_n, 0.0)
                self.assertEqual(new_wire.seismic_moment_nm, 0.0)
                self.assertEqual(new_wire.seismic_tension_n, 0.0)

                new_omni = new.evaluated_position_result.report_result
                old_north = old.report_result
                for field in (
                    "total_wind_load_n",
                    "resultant_wind_load_n",
                    "combined_wind_moment_nm",
                    "resultant_seismic_load_n",
                    "combined_seismic_moment_nm",
                ):
                    self.assertEqual(
                        getattr(new_omni, field), getattr(old_north, field)
                    )

    def test_seismic_total_excludes_ohw_for_all_three_standards(self):
        for code in (1, 2, 6):
            with self.subTest(code=code):
                result = new_workflow(code).calculate_at(0.0)
                expected = (
                    result.pole_aggregation.total_seismic_load_n
                    + result.direct_object_aggregation.total_seismic_load_n
                )
                self.assertAlmostEqual(
                    result.evaluated_position_result.total_seismic_load_n,
                    expected,
                )
                self.assertEqual(
                    result.overhead_wire_aggregation.total_seismic_load_n,
                    0.0,
                )
                self.assertEqual(
                    result.overhead_wire_aggregation.total_seismic_tension_n,
                    0.0,
                )

    def test_complete_result_contains_compression_bending_and_status(self):
        for code in (1, 2, 6):
            with self.subTest(code=code):
                result = new_workflow(code).calculate_at(0.0)
                stress = result.stress_result

                self.assertGreater(stress.bending_stress_n_mm2, 0)
                self.assertGreater(stress.compressive_stress_n_mm2, 0)
                self.assertGreaterEqual(stress.total_utilization_ratio, 0)
                self.assertIn(stress.status, {"O.K", "N.G"})

    def test_rejects_standard_outside_stage_eight_scope(self):
        standard = DesignStandardFactory.create(
            3,
            structure_height_m=8.15,
        )

        with self.assertRaisesRegex(ValueError, "only d_st 1, 2, and 6"):
            Standard126CalculationWorkflow(
                design_standard=standard,
                pole_assembly=PoleAssembly(_poles()),
                seismic_condition=SeismicCondition.ground(0.5),
            )

    def test_application_service_is_the_new_multi_position_caller(self):
        service = CalculationService(new_workflow(2))

        results = service.calculate((6.65, 1.65, 0.0))

        self.assertEqual(
            tuple(result.evaluated_position_result.evaluated_position_m for result in results),
            (6.65, 1.65, 0.0),
        )
        self.assertTrue(
            all(
                len(result.evaluated_position_result.directional_results) == 1
                for result in results
            )
        )


if __name__ == "__main__":
    unittest.main()
