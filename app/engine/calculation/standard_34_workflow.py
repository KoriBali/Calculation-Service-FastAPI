"""DesignStandard-object workflow for d_st 3 and 4.

Ported from python_calc ``calculation/standard_34_workflow.py`` (commit 270d23b).
"""

from collections.abc import Iterable
from math import fsum, hypot, radians

from app.engine.domain.conditions import SeismicCondition
from app.engine.domain.arm import ArmAssembly
from app.engine.domain.direct_object import DirectObject
from app.engine.domain.loads import OverdesignFactor
from app.engine.domain.overhead_wire import OverheadWire
from app.engine.domain.standards import DesignStandard, DesignStandardCode

from .direct_object_calculator import DirectObjectCalculator
from .arm_calculator import ArmAssemblyCalculator
from .overhead_wire_calculator import OverheadWireCalculator
from .pole_assembly import PoleAssembly
from .pole_calculator import PoleCalculator
from .result import Standard34CalculationResult, Standard34DirectionResult
from .rounding import CalculationValueType, rounding_profile_for
from .seismic import NoSeismicPolicy
from .standard_126_workflow import _StandardWindCondition
from .stress import SimpleBendingStressInput, SimpleBendingStressPolicy


class Standard34CalculationWorkflow:
    """Run bending-only straight/oblique calculations for d_st 3 and 4."""

    _SUPPORTED_CODES = {
        DesignStandardCode.OLD_LIGHTING_POLE,
        DesignStandardCode.SMALL_SIGN_BOARD,
    }

    def __init__(
        self,
        *,
        design_standard: DesignStandard,
        pole_assembly: PoleAssembly,
        direct_objects: Iterable[DirectObject] = (),
        overhead_wires: Iterable[OverheadWire] = (),
        arm_assembly: ArmAssembly | None = None,
        overdesign_factor: OverdesignFactor | None = None,
    ) -> None:
        if not isinstance(design_standard, DesignStandard):
            raise TypeError("design_standard must be a DesignStandard")
        if design_standard.code not in self._SUPPORTED_CODES:
            raise ValueError("This workflow supports only d_st 3 and 4")
        if design_standard.seismic_policy.enabled:
            raise NotImplementedError(
                "Optional special seismic calculation has not been prepared "
                "for d_st 3 or 4"
            )
        if not isinstance(design_standard.stress_policy, SimpleBendingStressPolicy):
            raise TypeError("d_st 3 and 4 require SimpleBendingStressPolicy")
        if (
            design_standard.code is DesignStandardCode.SMALL_SIGN_BOARD
            and arm_assembly is not None
            and arm_assembly.arm_parts
        ):
            raise ValueError("d_st = 4 does not use Arm calculation")

        self.design_standard = design_standard
        self.wind_condition = _StandardWindCondition(design_standard)
        self.rounding = rounding_profile_for(design_standard.code)
        no_seismic = NoSeismicPolicy()
        # SeismicCondition remains a compatibility dependency of the existing
        # object calculators. Its value is not used because NoSeismicPolicy is
        # supplied explicitly.
        compatibility_seismic_condition = SeismicCondition.ground(1.0)
        self.pole_calculator = PoleCalculator(
            assembly=pole_assembly,
            wind_condition=self.wind_condition,
            seismic_condition=compatibility_seismic_condition,
            overdesign_factor=overdesign_factor,
            seismic_policy=no_seismic,
        )
        self.direct_object_calculator = DirectObjectCalculator(
            direct_objects=direct_objects,
            wind_condition=self.wind_condition,
            seismic_condition=compatibility_seismic_condition,
            seismic_policy=no_seismic,
        )
        self.overhead_wire_calculator = OverheadWireCalculator(
            wires=overhead_wires,
            wind_condition=self.wind_condition,
            seismic_condition=compatibility_seismic_condition,
            seismic_policy=no_seismic,
            calculate_seismic_tension=False,
        )
        self.arm_assembly_calculator = (
            ArmAssemblyCalculator(arm_assembly, design_standard)
            if arm_assembly is not None
            else None
        )

    def calculate_at(self, evaluated_position_m: float) -> Standard34CalculationResult:
        pole = self.pole_calculator.aggregate_at(evaluated_position_m)
        if not pole.pole_results:
            raise ValueError(
                "EvaluatedPosition must be below the top of at least one Pole"
            )
        direct = self.direct_object_calculator.aggregate_at(evaluated_position_m)
        wire = self.overhead_wire_calculator.aggregate_at(evaluated_position_m)
        arm = (
            self.arm_assembly_calculator.aggregate_at(evaluated_position_m)
            if self.arm_assembly_calculator is not None
            else None
        )
        evaluated_pole_result = pole.pole_results[0]
        evaluated_pole = next(
            item
            for item in self.pole_calculator.assembly.poles
            if item.name == evaluated_pole_result.geometry.pole_name
        )
        section_properties = evaluated_pole_result.section_properties
        total_fix_load = self.rounding.apply(
            fsum((
                pole.total_fix_load_n,
                direct.total_fix_load_n,
                wire.total_fix_load_n,
                0.0 if arm is None else arm.total_fix_load_n,
            )),
            CalculationValueType.LOAD,
        )

        pole_by_direction = {
            item.direction: item for item in pole.directional_totals
        }
        direct_by_direction = {
            item.direction: item for item in direct.directional_totals
        }
        wire_by_direction = {
            item.direction: item for item in wire.directional_totals
        }
        arm_by_direction = (
            {item.direction: item for item in arm.directional_totals}
            if arm is not None
            else {}
        )
        direction_results = tuple(
            self._direction_result(
                name=case.name,
                angle_deg=case.angle_deg,
                pole=pole_by_direction[case.name],
                direct=direct_by_direction[case.name],
                wire=wire_by_direction[case.name],
                arm=arm_by_direction.get(case.name),
                section_modulus_cm3=section_properties.section_modulus_cm3,
                allowable_bending_n_mm2=(
                    evaluated_pole.material.short_term_allowable_bending
                ),
            )
            for case in self.design_standard.wind_case_policy.cases()
        )

        return Standard34CalculationResult(
            design_standard=self.design_standard,
            evaluated_position_m=float(evaluated_position_m),
            evaluated_pole_name=evaluated_pole.name,
            material_name=evaluated_pole.material.name,
            section_properties=section_properties,
            total_fix_load_n=total_fix_load,
            pole_aggregation=pole,
            direct_object_aggregation=direct,
            overhead_wire_aggregation=wire,
            direction_results=direction_results,
            arm_aggregation=arm,
        )

    def _direction_result(
        self,
        *,
        name,
        angle_deg,
        pole,
        direct,
        wire,
        arm,
        section_modulus_cm3,
        allowable_bending_n_mm2,
    ) -> Standard34DirectionResult:
        wind_load = self.rounding.apply(
            fsum((
                pole.total_wind_load_n,
                direct.total_wind_load_n,
                wire.total_wind_load_n,
                0.0 if arm is None else arm.total_wind_load_n,
            )),
            CalculationValueType.LOAD,
        )
        wind_x = self.rounding.apply(
            fsum((
                pole.total_wind_load_x_n,
                direct.total_wind_load_x_n,
                wire.total_wind_load_x_n,
                0.0 if arm is None else arm.total_wind_load_x_n,
            )),
            CalculationValueType.LOAD,
        )
        wind_y = self.rounding.apply(
            fsum((
                pole.total_wind_load_y_n,
                direct.total_wind_load_y_n,
                wire.total_wind_load_y_n,
                0.0 if arm is None else arm.total_wind_load_y_n,
            )),
            CalculationValueType.LOAD,
        )
        resultant_x = self.rounding.apply(
            wind_x + wire.total_wind_tension_x_n,
            CalculationValueType.LOAD,
        )
        resultant_y = self.rounding.apply(
            wind_y + wire.total_wind_tension_y_n,
            CalculationValueType.LOAD,
        )
        wind_moment_x = self.rounding.apply(
            fsum((
                pole.total_wind_moment_x_nm,
                direct.total_wind_moment_x_nm,
                wire.total_wind_moment_x_nm,
                0.0 if arm is None else arm.total_wind_moment_x_nm,
            )),
            CalculationValueType.MOMENT,
        )
        wind_moment_y = self.rounding.apply(
            fsum((
                pole.total_wind_moment_y_nm,
                direct.total_wind_moment_y_nm,
                wire.total_wind_moment_y_nm,
                0.0 if arm is None else arm.total_wind_moment_y_nm,
            )),
            CalculationValueType.MOMENT,
        )
        combined_x = self.rounding.apply(
            wind_moment_x
            + wire.total_wind_tension_moment_x_nm
            + (0.0 if arm is None else arm.total_fix_load_moment_x_nm),
            CalculationValueType.MOMENT,
        )
        combined_y = self.rounding.apply(
            wind_moment_y
            + wire.total_wind_tension_moment_y_nm
            + (0.0 if arm is None else arm.total_fix_load_moment_y_nm),
            CalculationValueType.MOMENT,
        )
        combined_moment = self.rounding.apply(
            hypot(combined_x, combined_y),
            CalculationValueType.MOMENT,
        )
        stress = self.design_standard.stress_policy.calculate(
            SimpleBendingStressInput(
                total_moment_nm=combined_moment,
                section_modulus_cm3=section_modulus_cm3,
                short_term_allowable_bending_n_mm2=allowable_bending_n_mm2,
            )
        )

        return Standard34DirectionResult(
            wind_case_name=name,
            wind_direction_deg=float(angle_deg),
            total_wind_load_n=wind_load,
            total_wind_load_x_n=wind_x,
            total_wind_load_y_n=wind_y,
            total_wind_tension_n=wire.total_wind_tension_n,
            resultant_wind_load_x_n=resultant_x,
            resultant_wind_load_y_n=resultant_y,
            resultant_wind_load_n=self.rounding.apply(
                hypot(resultant_x, resultant_y),
                CalculationValueType.LOAD,
            ),
            combined_wind_moment_x_nm=combined_x,
            combined_wind_moment_y_nm=combined_y,
            combined_wind_moment_nm=combined_moment,
            bending_stress=stress,
        )
