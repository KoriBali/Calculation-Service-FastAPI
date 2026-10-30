"""Complete Arm-enabled workflows for design standards 5, 7 and 9.

Ported from python_calc ``calculation/standard_arm_workflows.py`` (commit 270d23b).
"""

from collections.abc import Iterable
from math import fsum, hypot, pi

from app.engine.domain.arm import ArmAssembly
from app.engine.domain.conditions import SeismicCondition
from app.engine.domain.direct_object import DirectObject
from app.engine.domain.loads import OverdesignFactor
from app.engine.domain.overhead_wire import OverheadWire
from app.engine.domain.standards import DesignStandard, DesignStandardCode

from .arm_calculator import ArmAssemblyCalculator
from .direct_object_calculator import DirectObjectCalculator
from .overhead_wire_calculator import OverheadWireCalculator
from .pole_assembly import PoleAssembly
from .pole_calculator import PoleCalculator
from .result import (
    Standard5CalculationResult,
    Standard7CalculationResult,
    Standard9CalculationResult,
    StandardDirectionalLoadResult,
)
from .rounding import CalculationValueType, rounding_profile_for
from .standard_126_workflow import _StandardWindCondition
from .stress import (
    LargeSignPoleStressInput,
    LargeSignPoleStressPolicy,
    NewJILPoleStressInput,
    NewJILPoleStressPolicy,
    OldTrafficSignalPoleStressInput,
    OldTrafficSignalPoleStressPolicy,
)


class _ArmEnabledWorkflow:
    """Shared aggregation only; each public workflow owns its stress method."""

    expected_code: DesignStandardCode
    expected_stress_policy: type

    def __init__(
        self,
        *,
        design_standard: DesignStandard,
        pole_assembly: PoleAssembly,
        arm_assembly: ArmAssembly,
        direct_objects: Iterable[DirectObject] = (),
        overhead_wires: Iterable[OverheadWire] = (),
        overdesign_factor: OverdesignFactor | None = None,
    ) -> None:
        if not isinstance(design_standard, DesignStandard):
            raise TypeError("design_standard must be a DesignStandard")
        if design_standard.code is not self.expected_code:
            raise ValueError(
                f"This workflow supports only d_st = {int(self.expected_code)}"
            )
        if not isinstance(design_standard.stress_policy, self.expected_stress_policy):
            raise TypeError(
                f"d_st = {int(self.expected_code)} has an incompatible stress policy"
            )
        if not isinstance(arm_assembly, ArmAssembly):
            raise TypeError("arm_assembly must be an ArmAssembly")

        self.design_standard = design_standard
        self.rounding = rounding_profile_for(design_standard.code)
        wind_condition = _StandardWindCondition(design_standard)
        compatibility_seismic = SeismicCondition.ground(1.0)
        self.pole_calculator = PoleCalculator(
            assembly=pole_assembly,
            wind_condition=wind_condition,
            seismic_condition=compatibility_seismic,
            overdesign_factor=overdesign_factor,
            seismic_policy=design_standard.seismic_policy,
        )
        self.direct_object_calculator = DirectObjectCalculator(
            direct_objects=direct_objects,
            wind_condition=wind_condition,
            seismic_condition=compatibility_seismic,
            seismic_policy=design_standard.seismic_policy,
        )
        self.overhead_wire_calculator = OverheadWireCalculator(
            wires=overhead_wires,
            wind_condition=wind_condition,
            seismic_condition=compatibility_seismic,
            seismic_policy=design_standard.seismic_policy,
            calculate_seismic_tension=(
                design_standard.code is DesignStandardCode.NEW_JIL
            ),
        )
        self.arm_assembly_calculator = ArmAssemblyCalculator(
            arm_assembly,
            design_standard,
        )

    def _aggregate(self, evaluated_position_m: float):
        pole = self.pole_calculator.aggregate_at(evaluated_position_m)
        if not pole.pole_results:
            raise ValueError(
                "EvaluatedPosition must be below the top of at least one Pole"
            )
        direct = self.direct_object_calculator.aggregate_at(evaluated_position_m)
        wire = self.overhead_wire_calculator.aggregate_at(evaluated_position_m)
        arm = self.arm_assembly_calculator.aggregate_at(evaluated_position_m)
        evaluated_pole_result = pole.pole_results[0]
        evaluated_pole = next(
            item
            for item in self.pole_calculator.assembly.poles
            if item.name == evaluated_pole_result.geometry.pole_name
        )

        total_fix_load = self._sum(
            (
                pole.total_fix_load_n,
                direct.total_fix_load_n,
                wire.total_fix_load_n,
                arm.total_fix_load_n,
            ),
            CalculationValueType.LOAD,
        )
        total_seismic_load = self._sum(
            (
                pole.total_seismic_load_n,
                direct.total_seismic_load_n,
                wire.total_seismic_load_n,
                arm.total_seismic_load_n,
            ),
            CalculationValueType.LOAD,
        )
        total_seismic_moment = self._sum(
            (
                pole.total_seismic_moment_nm,
                direct.total_seismic_moment_nm,
                wire.total_seismic_moment_nm,
                arm.total_seismic_moment_nm,
            ),
            CalculationValueType.MOMENT,
        )

        pole_by_direction = {item.direction: item for item in pole.directional_totals}
        direct_by_direction = {
            item.direction: item for item in direct.directional_totals
        }
        wire_by_direction = {item.direction: item for item in wire.directional_totals}
        arm_by_direction = {item.direction: item for item in arm.directional_totals}
        directions = tuple(
            self._direction_result(
                case.name,
                case.angle_deg,
                pole_by_direction[case.name],
                direct_by_direction[case.name],
                wire_by_direction[case.name],
                arm_by_direction[case.name],
                total_seismic_moment,
            )
            for case in self.design_standard.wind_case_policy.cases()
        )
        return (
            pole,
            direct,
            wire,
            arm,
            evaluated_pole_result,
            evaluated_pole,
            total_fix_load,
            total_seismic_load,
            total_seismic_moment,
            directions,
        )

    def _direction_result(
        self,
        name,
        angle_deg,
        pole,
        direct,
        wire,
        arm,
        total_seismic_moment_nm,
    ) -> StandardDirectionalLoadResult:
        wind_load = self._sum(
            (
                pole.total_wind_load_n,
                direct.total_wind_load_n,
                wire.total_wind_load_n,
                arm.total_wind_load_n,
            ),
            CalculationValueType.LOAD,
        )
        wind_x = self._sum(
            (
                pole.total_wind_load_x_n,
                direct.total_wind_load_x_n,
                wire.total_wind_load_x_n,
                arm.total_wind_load_x_n,
            ),
            CalculationValueType.LOAD,
        )
        wind_y = self._sum(
            (
                pole.total_wind_load_y_n,
                direct.total_wind_load_y_n,
                wire.total_wind_load_y_n,
                arm.total_wind_load_y_n,
            ),
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
        fix_x = arm.total_fix_load_moment_x_nm
        fix_y = arm.total_fix_load_moment_y_nm
        fix_moment = self.rounding.apply(
            hypot(fix_x, fix_y), CalculationValueType.MOMENT
        )
        wind_moment_x = self._sum(
            (
                pole.total_wind_moment_x_nm,
                direct.total_wind_moment_x_nm,
                wire.total_wind_moment_x_nm,
                arm.total_wind_moment_x_nm,
                wire.total_wind_tension_moment_x_nm,
                fix_x,
            ),
            CalculationValueType.MOMENT,
        )
        wind_moment_y = self._sum(
            (
                pole.total_wind_moment_y_nm,
                direct.total_wind_moment_y_nm,
                wire.total_wind_moment_y_nm,
                arm.total_wind_moment_y_nm,
                wire.total_wind_tension_moment_y_nm,
                fix_y,
            ),
            CalculationValueType.MOMENT,
        )
        combined_wind = self.rounding.apply(
            hypot(wind_moment_x, wind_moment_y),
            CalculationValueType.MOMENT,
        )
        seismic_without_fix = self.rounding.apply(
            total_seismic_moment_nm
            + abs(wire.total_seismic_tension_moment_nm),
            CalculationValueType.MOMENT,
        )
        combined_seismic = self.rounding.apply(
            hypot(fix_moment, seismic_without_fix),
            CalculationValueType.MOMENT,
        )
        return StandardDirectionalLoadResult(
            wind_case_name=name,
            wind_direction_deg=float(angle_deg),
            total_wind_load_n=wind_load,
            total_wind_load_x_n=wind_x,
            total_wind_load_y_n=wind_y,
            resultant_wind_load_x_n=resultant_x,
            resultant_wind_load_y_n=resultant_y,
            resultant_wind_load_n=self.rounding.apply(
                hypot(resultant_x, resultant_y), CalculationValueType.LOAD
            ),
            moment_due_to_fix_load_x_nm=fix_x,
            moment_due_to_fix_load_y_nm=fix_y,
            moment_due_to_fix_load_nm=fix_moment,
            combined_wind_moment_x_nm=wind_moment_x,
            combined_wind_moment_y_nm=wind_moment_y,
            combined_wind_moment_nm=combined_wind,
            wind_torsional_moment_nm=arm.total_wind_torque_nm,
            combined_seismic_moment_nm=combined_seismic,
            seismic_torsional_moment_nm=arm.total_seismic_torque_nm,
        )

    def _sum(self, values, value_type):
        return self.rounding.apply(fsum(values), value_type)


class Standard5CalculationWorkflow(_ArmEnabledWorkflow):
    """Large sign board: straight/oblique, compression and torsion."""

    expected_code = DesignStandardCode.LARGE_SIGN_BOARD
    expected_stress_policy = LargeSignPoleStressPolicy

    def calculate_at(self, evaluated_position_m: float) -> Standard5CalculationResult:
        data = self._aggregate(evaluated_position_m)
        pole, direct, wire, arm = data[:4]
        pole_result, evaluated_pole = data[4:6]
        total_fix, directions = data[6], data[9]
        if not arm.arm_results:
            raise ValueError("d_st = 5 requires an active Arm above EvaluatedPosition")
        arm_heights = {
            item.installation_height_m for item in arm.arm_results
        }
        if len(arm_heights) != 1:
            raise ValueError(
                "d_st = 5 buckling reference is ambiguous when active Arms "
                "have different installation heights"
            )
        by_name = {item.wind_case_name: item for item in directions}
        section = pole_result.section_properties
        stress = self.design_standard.stress_policy.calculate(
            LargeSignPoleStressInput(
                total_fix_load_n=total_fix,
                straight_total_bending_moment_nm=(
                    by_name["STRAIGHT"].combined_wind_moment_nm
                ),
                straight_total_torsional_moment_nm=(
                    by_name["STRAIGHT"].wind_torsional_moment_nm
                ),
                oblique_total_bending_moment_nm=(
                    by_name["OBLIQUE"].combined_wind_moment_nm
                ),
                oblique_total_torsional_moment_nm=(
                    by_name["OBLIQUE"].wind_torsional_moment_nm
                ),
                arm_height_m=next(iter(arm_heights)),
                evaluated_position_m=float(evaluated_position_m),
                pole_diameter_mm=section.diameter_mm,
                cross_section_area_cm2=section.cross_section_area_cm2,
                moment_of_inertia_cm4=section.moment_of_inertia_cm4,
                section_modulus_cm3=section.section_modulus_cm3,
                radius_of_gyration_cm=section.radius_of_gyration_cm,
                short_term_allowable_bending_n_mm2=(
                    evaluated_pole.material.short_term_allowable_bending
                ),
                short_term_allowable_shear_n_mm2=(
                    evaluated_pole.material.require_shear()
                ),
            )
        )
        return Standard5CalculationResult(
            design_standard=self.design_standard,
            evaluated_position_m=float(evaluated_position_m),
            evaluated_pole_name=evaluated_pole.name,
            material_name=evaluated_pole.material.name,
            section_properties=section,
            total_fix_load_n=total_fix,
            pole_aggregation=pole,
            direct_object_aggregation=direct,
            overhead_wire_aggregation=wire,
            arm_aggregation=arm,
            direction_results=directions,
            stress_result=stress,
        )


class Standard7CalculationWorkflow(_ArmEnabledWorkflow):
    """New JIL: full eight-direction wind and seismic Arm calculation."""

    expected_code = DesignStandardCode.NEW_JIL
    expected_stress_policy = NewJILPoleStressPolicy

    def calculate_at(self, evaluated_position_m: float) -> Standard7CalculationResult:
        data = self._aggregate(evaluated_position_m)
        pole, direct, wire, arm = data[:4]
        pole_result, evaluated_pole = data[4:6]
        total_fix, total_seismic, total_seismic_moment, directions = data[6:10]
        section = pole_result.section_properties
        stress = self.design_standard.stress_policy.calculate(
            NewJILPoleStressInput(
                moments_due_to_fixload_nm=tuple(
                    item.moment_due_to_fix_load_nm for item in directions
                ),
                combined_wind_moments_nm=tuple(
                    item.combined_wind_moment_nm for item in directions
                ),
                wind_torsional_moments_nm=tuple(
                    item.wind_torsional_moment_nm for item in directions
                ),
                combined_seismic_moments_nm=tuple(
                    item.combined_seismic_moment_nm for item in directions
                ),
                seismic_torsional_moments_nm=tuple(
                    item.seismic_torsional_moment_nm for item in directions
                ),
                pole_diameter_mm=section.diameter_mm,
                moment_of_inertia_cm4=section.moment_of_inertia_cm4,
                section_modulus_cm3=section.section_modulus_cm3,
                allowable_bending_n_mm2=evaluated_pole.material.allowable_bending,
                short_term_allowable_bending_n_mm2=(
                    evaluated_pole.material.short_term_allowable_bending
                ),
                short_term_allowable_shear_n_mm2=(
                    evaluated_pole.material.require_shear()
                ),
            )
        )
        return Standard7CalculationResult(
            design_standard=self.design_standard,
            evaluated_position_m=float(evaluated_position_m),
            evaluated_pole_name=evaluated_pole.name,
            material_name=evaluated_pole.material.name,
            section_properties=section,
            total_fix_load_n=total_fix,
            total_seismic_load_n=total_seismic,
            total_seismic_moment_nm=total_seismic_moment,
            pole_aggregation=pole,
            direct_object_aggregation=direct,
            overhead_wire_aggregation=wire,
            arm_aggregation=arm,
            direction_results=directions,
            stress_result=stress,
        )


class Standard9CalculationWorkflow(_ArmEnabledWorkflow):
    """Old traffic signal: eight-direction bending and torsion, no seismic."""

    expected_code = DesignStandardCode.OLD_TRAFFIC_SIGNAL
    expected_stress_policy = OldTrafficSignalPoleStressPolicy

    def calculate_at(self, evaluated_position_m: float) -> Standard9CalculationResult:
        data = self._aggregate(evaluated_position_m)
        pole, direct, wire, arm = data[:4]
        pole_result, evaluated_pole = data[4:6]
        total_fix, directions = data[6], data[9]
        section = pole_result.section_properties
        stress = self.design_standard.stress_policy.calculate(
            OldTrafficSignalPoleStressInput(
                total_bending_moments_nm=tuple(
                    item.combined_wind_moment_nm for item in directions
                ),
                total_torsional_moments_nm=tuple(
                    item.wind_torsional_moment_nm for item in directions
                ),
                pole_diameter_mm=section.diameter_mm,
                moment_of_inertia_cm4=section.moment_of_inertia_cm4,
                section_modulus_cm3=section.section_modulus_cm3,
                short_term_allowable_bending_n_mm2=(
                    evaluated_pole.material.short_term_allowable_bending
                ),
                short_term_allowable_shear_n_mm2=(
                    evaluated_pole.material.require_shear()
                ),
            )
        )
        return Standard9CalculationResult(
            design_standard=self.design_standard,
            evaluated_position_m=float(evaluated_position_m),
            evaluated_pole_name=evaluated_pole.name,
            material_name=evaluated_pole.material.name,
            section_properties=section,
            total_fix_load_n=total_fix,
            pole_aggregation=pole,
            direct_object_aggregation=direct,
            overhead_wire_aggregation=wire,
            arm_aggregation=arm,
            direction_results=directions,
            stress_result=stress,
        )
